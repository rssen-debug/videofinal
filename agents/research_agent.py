#!/usr/bin/env python3
"""agents/research_agent.py — samlar fakta från flera källor och bygger
research.json med claims (typ + tier + confidence).

Källhierarki (tier):
 1 official/court/company/gov/direct  — bevis OK
 2 major news / etablerade publikationer — bevis OK
 3 specialistpublikationer
 4 reddit/x/forum — ENBART lead discovery
 5 random webb — ENBART lead discovery

Med LLM: anrikar [1] med fler queries + extract -> claims + extraherade siffror.
Utan LLM: dependable Wikipedia + Google News -> claims (märkta som CLAIM/INFERENCE).
"""
import os, re, json, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from research import sources as S
from research import claims as C
from agents import llm

MAX_CLAIMS = 120

def _iso_date():
    return datetime.date.today().isoformat()

def _facts_from_extract(topic, title, extract):
    """Plocka ut meningar med siffror/namn som kandidat-claims."""
    sents = re.split(r"(?<=[.!?])\s+", extract)
    out = []
    for s in sents:
        s = s.strip()
        if len(s) < 30 or len(s) > 300:
            continue
        if not re.search(r"\d", s):
            continue
        out.append(C.make_claim(
            claim=s, source="wikipedia", url=
            f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            date=_iso_date(), evidence=s, confidence=0.85,
            kind="FACT" if re.search(r"\b(was|is|in|on|at)\b", s) else "CLAIM",
            tier=2, query=topic))
    return out

def _news_claims(topic):
    out = []
    for item in S.news_rss(topic, count=8):
        title = (item["title"] or "").strip()
        if not title:
            continue
        src = (item["source"] or "google-news").strip()
        # Googles RSS lägger " - Källa" i slutet av titeln — kapa bort det
        if src and title.lower().endswith(" - " + src.lower()):
            title = title[:-(len(" - " + src))].strip()
        out.append(C.make_claim(
            claim=title, source=src,
            url=item["url"], date=item["published"],
            evidence=title, confidence=0.6,
            kind="CLAIM", tier=3, query=topic))
    return out

def _llm_claims(topic, extract, news):
    try:
        prompt = f"""Du är research-agent i en dokumentär-studio. Ämne: {topic}.

Skriv en JSON-lista med research-claims. VARJE claim = en specifik, faktisk
uppgift (siffror, datum, namn, händelser, citat) som kan bära ett manus-block.

Material att extrahera ur (text):
{extract[:6000]}

Nyhetsrubriker:
{json.dumps(news[:10], ensure_ascii=False)[:2500]}

Svara INGET annat än JSON-array av objekt:
[{{"claim":"...","source":"...","url":"...","date":"...","confidence":0.0-1.0,
   "kind":"FACT|CLAIM|ALLEGATION|OPINION|INFERENCE|RUMOR","tier":1-5}}]

Regler: kom aldrig på fakta; använd bara materialet. "tier" från källans typ.
Hitta också 4-6 NYA sök-frågor (entity-namn, "vs", "controversy") och lägg dem
separat: {{"queries":[...]}}."""
        obj = llm.fill_json(prompt, system="Du returnerar bara JSON.")
        assert obj is not None
        queries = obj.pop("queries", []) if isinstance(obj, dict) else []
        arr = obj if isinstance(obj, list) else obj.get("claims", [])
    except Exception:
        return [], []
    out = []
    for c in arr:
        if not isinstance(c, dict) or not c.get("claim"):
            continue
        out.append(C.make_claim(
            claim=c["claim"], source=c.get("source", "llm"),
            url=c.get("url", ""), date=c.get("date", _iso_date()),
            evidence=c.get("evidence", "") , confidence=c.get("confidence", 0.7),
            kind=c.get("kind", "CLAIM"), tier=c.get("tier", 3), query=topic))
    return out, queries

def run(topic, project_dir, max_queries=5):
    """Returnerar research.json (payload) och skriver den till disk."""
    queries = [topic]
    facts, seen, sources = [], set(), []

    # pass 1: wikipedia summary/extract
    ext_for_llm = ""
    try:
        ws = S.wikipedia_search(topic)
        if ws["titles"]:
            title = ws["titles"][0]
            summ = S.wikipedia_summary(title)
            ext = S.wikipedia_extract(title)
            ext_for_llm = ext
            sources.append({"type": "wikipedia", "title": title,
                            "url": summ.get("url", ""), "tier": 2})
            for c in _facts_from_extract(topic, title, ext if ext else summ.get("extract", "")):
                k = c["claim"][:120]
                if k not in seen and len(facts) < MAX_CLAIMS:
                    seen.add(k); facts.append(c)
            # "Vem"-fråga för att hitta närliggande sidor
            m = re.search(r"\b(is|was)\s+(a|an|the)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,3})", summ.get("extract", ""))
            if m:
                queries.append(m.group(3))
    except Exception:
        pass

    # pass 2: news
    for c in _news_claims(topic):
        k = c["claim"][:120]
        if k not in seen and len(facts) < MAX_CLAIMS:
            seen.add(k); facts.append(c)

    # pass 3 (LLM): extraktion + nya queries
    extra_queries = []
    if llm.is_available():
        facts2, extra_queries = _llm_claims(topic, ext_for_llm, facts)
        for c in facts2:
            k = c["claim"][:120]
            if k not in seen and len(facts) < MAX_CLAIMS:
                seen.add(k); facts.append(c)
    for q in (extra_queries + queries)[:max_queries]:
        if q.lower() == topic.lower():
            continue
        for c in _news_claims(q):
            k = c["claim"][:120]
            if k not in seen and len(facts) < MAX_CLAIMS:
                seen.add(k); facts.append(c)
        try:
            ws = S.wikipedia_search(q)
            if ws["titles"]:
                ext = S.wikipedia_summary(ws["titles"][0]).get("extract", "")
                for c in _facts_from_extract(topic, ws["titles"][0], ext):
                    k = c["claim"][:120]
                    if k not in seen and len(facts) < MAX_CLAIMS:
                        seen.add(k); facts.append(c)
        except Exception:
            pass

    payload = C.new_research(topic)
    payload["generated"] = _iso_date()
    payload["facts"] = facts[:MAX_CLAIMS]
    payload["sources"] = sources
    payload["stats"] = {
        "total_claims": len(facts),
        "facts": sum(1 for f in facts if f["kind"] == "FACT"),
        "allegations": sum(1 for f in facts if f["kind"] == "ALLEGATION"),
        "tier1_2": sum(1 for f in facts if f["tier"] <= 2),
        "tier4_5": sum(1 for f in facts if f["tier"] >= 4),
    }
    os.makedirs(project_dir, exist_ok=True)
    C.save_research(os.path.join(project_dir, "research.json"), payload)
    return payload
