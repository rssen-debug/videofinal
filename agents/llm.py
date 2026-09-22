#!/usr/bin/env python3
"""llm.py — LLM-skal (OpenAI/Groq/valfri OpenAI-kompatibel leverantör) +
deterministisk JSON-parsning + offline-fallback.

END POINT:
  OPENAI_API_KEY (openai/groq)  → LLM.fill(prompt, max_tokens)
  GROQ_API_KEY                  → samma, med base_url https://api.groq.com/openai/v1
  SUNNY_LLM_URL + SUNNY_LLM_KEY → valfri OpenAI-kompatibel endpoint
  --no-llm                      → is_available() == False (heuristics = hjärnan)

JSON-parsning är robust: extraherar första balanserade {..} eller [..] block
och tolererar markdown-fences / friformstext runt JSON.
"""
import os, re, json

DEFAULT_MODEL = "gpt-4o-mini"

class LLMError(RuntimeError):
    pass

def _key():
    return (os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY")
            or os.environ.get("SUNNY_LLM_KEY") or "").strip()

def _base_url():
    if os.environ.get("GROQ_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        return "https://api.groq.com/openai/v1"
    return os.environ.get("SUNNY_LLM_URL") or os.environ.get("OPENAI_BASE_URL") or None

def is_available():
    return bool(_key())

def model():
    return os.environ.get("SUNNY_LLM_MODEL") or DEFAULT_MODEL

def fill(prompt, max_tokens=3000, temperature=None, system=None):
    """Synkron textkomplettering. Returnerar strängen (utan kringliggande JSON)."""
    if not _key():
        raise LLMError("ingen LLM-nyckel — sätt OPENAI_API_KEY / GROQ_API_KEY")
    import requests
    body = {"model": model(), "messages": []}
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    body["max_tokens"] = max_tokens
    body["temperature"] = temperature
    headers = {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}
    url = (_base_url() or "https://api.openai.com/v1") + "/chat/completions"
    r = requests.post(url, json=body, headers=headers, timeout=180)
    if r.status_code != 200:
        raise LLMError(f"LLM {r.status_code}: {r.text[:400]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"LLM-svar oläsbart: {e}")

# ---------------- JSON-parsning ----------------
def _first_balanced_block(s, open_ch, close_ch):
    i = s.find(open_ch)
    if i < 0:
        return None
    depth, esc, in_str = 0, False, False
    for j in range(i, len(s)):
        c = s[j]
        if esc:
            esc = False; continue
        if c == "\\":
            esc = True; continue
        if c == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return s[i:j + 1]
    return None

def parse_json(text):
    """Returnerar (objekt | None)."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*", "", t).strip()
        t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    block = _first_balanced_block(t, "{", "}") or _first_balanced_block(t, "[", "]")
    if block:
        try:
            return json.loads(block)
        except Exception:
            pass
    return None

def fill_json(prompt, max_tokens=4000, system=None, required_keys=()):
    """fill + parse_json. Vid tomt svar returneras None (anroparen faller tillbaka)."""
    try:
        txt = fill(prompt, max_tokens=max_tokens, system=system)
    except LLMError as e:
        raise
    obj = parse_json(txt)
    if obj is not None and isinstance(obj, dict):
        missing = [k for k in required_keys if k not in obj]
        if not missing:
            return obj
    return None
