#!/usr/bin/env python3
"""agents/factcheck_agent.py — kontrollerar manuset mot research.json.

Varje block: siffror/datum/namn-kandidater matchas mot claims (evidence+source).
Os­tödda påståenden -> fixong via LLM (rewrite/ta bort) eller flagga.
Skriver factcheck.json och returnerar (ok_status, åtgärdat script).
"""
import os, json, re
from research import claims as C
from agents import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_NAME_RE = re.compile(r"\b[A-Z][a-zA-Z']{2,}(?:\s[A-Z][a-zA-Z']{2,}){0,2}\b")

# vanliga engelska ord som aldrig ska flaggas (meningsinitial rad etc.)
_STOPWORDS = {w.lower() for w in """
    a an the and or but if then else for nor so yet of to in on at by with from as
    is was are were be been being have has had do does did this that these those it
    its he she they them we you your i me my his her their there here where when
    what which who whom why how all any each every both few more most other some
    no not only own same such than too very just about above after again against
    along also always among because before between both but can could during even
    ever every first however into just last like made make many may might much
    must never now once one said should still take than that then there these they
    thing think this those though through time under until upon used very want way
    well went were what when where which while who why will with would yes yet you
    your everyone nobody somebody someone everything nothing something anything
    stick subscribe look listen said it couldn it's wasnt those they're
""".split()}

def _symp(c):
    return (c.get("claim", "") + " " + c.get("source", "")) .lower()

def check_block(text, facts):
    """Returnerar {unsupported_numbers, unsupported_names, ok_len, flags}."""
    numbers = C.numbers_in(text)
    bad_n, bad_name = [], []
    for n in numbers:
        if not any(n.lower() in _symp(f) for f in facts):
            bad_n.append(n)
    # meningsgränser: hoppa över meningsinitialt ord (stor bokstav pga syntax)
    sentence_starts = {m.end() for m in re.finditer(r"(^|[.!?]\s+)", text)}
    for m in _NAME_RE.finditer(text):
        nm = m.group(0)
        low = nm.lower()
        if low in _STOPWORDS:
            continue
        if m.start() in sentence_starts and len(nm.split()) == 1:
            continue  # meningsinitial
        # flerordsnamn vars samtliga delar är stopord = generisk fras
        if all(w.lower() in _STOPWORDS for w in nm.split()):
            continue
        if not any(low in _symp(f) for f in facts):
            bad_name.append(nm)
    flags = []
    if bad_n:
        flags.append(f"os­tödda siffror: {', '.join(bad_n)}")
    if bad_name:
        flags.append(f"os­tödda namn: {', '.join(bad_name[:6])}")
    return {"numbers": bad_n, "names": bad_name, "flags": flags}

def run(plan, research, project_dir, rewrite_with_llm=True):
    facts = research["facts"]
    checks, ok_all = [], True
    for b in plan.get("blocks", []):
        c = check_block(b.get("voiceover", ""), facts)
        c["id"] = b["id"]
        checks.append(c)
        if c["flags"]:
            ok_all = False
    report = {"ok": ok_all, "blocks": checks}
    if ok_all:
        "pass"
    elif rewrite_with_llm and llm.is_available():
        # LLM fixar: ta bort/ändra os­tödda formuleringar
        try:
            ctx = {"plan": plan, "problems": checks}
            prompt = ("Du fixar ett manus så att VARJE påstående stöds av research.\n"
                      "Om en siffra/namn inte stöds: ändra formuleringen eller ta bort.\n"
                      "Behåll style/pacing. Returnera STRICT JSON med ny \"blocks\"-lista\n"
                      f"(samma nycklar). Problem: {json.dumps(checks, ensure_ascii=False)}\n"
                      f"Manus: {json.dumps(plan, ensure_ascii=False)[:9000]}")
            obj = llm.fill_json(prompt, required_keys=["blocks"])
            if obj:
                for b in obj["blocks"]:
                    b.setdefault("music", "MEDIUM"); b.setdefault("visuals", [])
                plan["blocks"] = obj["blocks"]
                report["rewritten"] = True
                # re-verify snabbt
                ok_all = True
                for b in plan["blocks"]:
                    c = check_block(b.get("voiceover", ""), facts)
                    c["id"] = b["id"]; checks.append(c)
                    if c["flags"]:
                        ok_all = False
                report["ok"] = ok_all
                report["blocks"] = checks
        except Exception:
            report["rewrite_error"] = True
    else:
        report["pending_manual"] = not ok_all

    if not ok_all:
        report["safe"] = False
    else:
        report["safe"] = True

    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "factcheck.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report, plan
