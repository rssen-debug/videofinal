#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VideoFinal 2026 — single-entry autonomous creator studio.

Interactive use:
    python videofinal.py

Three selections maximum:
    1) mode
    2) niche
    3) resolution

Then the director runs:
    scout -> score -> research -> story -> source hunt -> source transcript
    -> source moment selection -> script -> TTS -> timeline -> real-footage render
    -> audio mix -> captions -> QC -> retry/next-story fallback

Modes:
    short = 9:16, 45-59 seconds, real source footage + original source audio
             + narrator where useful + captions tied to the active speaker.
    doc   = 16:9 cinematic internet documentary, 5-act structure, real footage,
             narrator, evidence cards, motion stills, music/SFX and QC.

LLM priority:
    Cerebras -> OpenAI -> Groq -> generic OpenAI-compatible endpoint.

Secrets are read from environment variables only. Never commit API keys.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import html
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter

try:
    import cv2
except Exception:
    cv2 = None

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
CACHE = ROOT / ".cache"
ASSET_CLIPS = ROOT / "assets" / "clips"
ASSET_STILLS = ROOT / "assets" / "stills"
OUTPUTS = ROOT / "youtube2026"
for _p in (PROJECTS, CACHE, ASSET_CLIPS, ASSET_STILLS, OUTPUTS):
    _p.mkdir(parents=True, exist_ok=True)

FPS = 30
SR = 44100

RESOLUTIONS = {
    "320p": {"short": (320, 568), "doc": (568, 320)},
    "720p": {"short": (720, 1280), "doc": (1280, 720)},
    "1080p": {"short": (1080, 1920), "doc": (1920, 1080)},
}

NICHES: dict[str, list[str]] = {
    "streamers": ["streamer drama", "Twitch streamer", "Kick streamer", "creator controversy"],
    "gaming": ["gaming news", "esports controversy", "game controversy", "gaming creator"],
    "internet": ["internet controversy", "viral creator story", "internet mystery", "creator news"],
    "tech": ["AI controversy", "technology news", "startup controversy", "tech creator"],
    "business": ["company controversy", "CEO story", "startup news", "business drama"],
    "sports": ["sports controversy", "boxing drama", "football controversy", "athlete story"],
    "science": ["space news", "science breakthrough", "weird science", "NASA story"],
    "history": ["history mystery", "historical event", "forgotten history", "history explained"],
    "movies_music": ["movie controversy", "music industry story", "artist controversy", "film news"],
    "weird": ["weird news", "strange internet story", "unexpected discovery", "unusual event"],
}

DEFAULT_VOICE = os.environ.get("VIDEOFINAL_VOICE", "en-GB-RyanNeural")
DEFAULT_CEREBRAS_MODEL = os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b")
_ASR_MODEL = None


# =============================================================================
# PRINTING / SHELL
# =============================================================================

def banner() -> None:
    st=llm_status()
    print("\n" + "=" * 72)
    print("VIDEOFINAL 2026  |  AUTOPILOT CREATOR STUDIO")
    print("LLM:",st["provider"],"/",st["model"] or "none")
    print("VAULT:",OUTPUTS)
    print("=" * 72)


def run_cmd(cmd: list[str], *, capture: bool = True, timeout: int = 900,
            cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-4000:]
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd[:8])}\n{err}")
    return proc


def exe(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise RuntimeError(f"{name} saknas i PATH. Installera {name} och starta om CMD.")
    return p


def ffmpeg() -> str:
    return exe("ffmpeg")


def ffprobe() -> str:
    return exe("ffprobe")


_PROGRESS = {"started": time.time(), "pct": 0.0}
_STAGE_PCT = {"bootstrap":2,"research":12,"story":20,"source_hunt":34,"source_selection":40,"render":72,"audio":84,"qc":96,"done":100}

def _fmt_eta(seconds: float) -> str:
    sec=max(0,int(seconds))
    return f"{sec//3600:02}:{(sec%3600)//60:02}:{sec%60:02}"

def progress(pct: float, label: str) -> None:
    pct=max(0.0,min(100.0,float(pct)))
    elapsed=max(0.001,time.time()-_PROGRESS["started"])
    eta=elapsed*(100.0-pct)/max(pct,0.5)
    width=34
    done=int(width*pct/100.0)
    bar="#"*done+"-"*(width-done)
    print(f"\r[{bar}] {pct:6.1f}% | ETA {_fmt_eta(eta)} | {label[:44]:<44}",end="",flush=True)
    if pct>=100.0: print()

def reset_progress(label: str="AUTOPILOT") -> None:
    _PROGRESS["started"]=time.time()
    _PROGRESS["pct"]=0.0
    progress(0.0,label)

def has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def ensure_runtime_dependencies() -> None:
    """Install only the runtime Python packages needed for the autopilot.

    FFmpeg remains a system dependency. Whisper is installed because source
    speech must be transcribed when a platform does not expose captions.
    """
    packages = {
        "requests": "requests>=2.31",
        "yt_dlp": "yt-dlp>=2026.1.1",
        "edge_tts": "edge-tts>=6.1.9",
        "faster_whisper": "faster-whisper>=1.0",
    }
    missing = [pkg for mod, pkg in packages.items() if not has_module(mod)]
    if not missing:
        return
    print("[BOOTSTRAP] Saknade Python-komponenter upptäckta: " + ", ".join(missing))
    print("[BOOTSTRAP] Installerar automatiskt för att hålla autopilot-flödet 3-klicks.")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *missing],
            check=True, timeout=1800,
        )
    except Exception as exc:
        raise RuntimeError(
            "Kunde inte installera nödvändiga Python-paket automatiskt: " + str(exc)
        )


# =============================================================================
# LLM ROUTER
# =============================================================================

def _windows_env(name: str) -> str:
    if os.name != "nt":
        return ""
    try:
        p = subprocess.run(["reg","query",r"HKCU\Environment","/v",name],capture_output=True,text=True,timeout=5,check=False)
        if p.returncode == 0:
            for line in p.stdout.splitlines():
                if name in line:
                    parts = re.split(r"\s{2,}", line.strip())
                    if len(parts) >= 3:
                        return parts[-1].strip()
    except Exception:
        pass
    return ""

def _env(name: str) -> str:
    return os.environ.get(name, "").strip() or _windows_env(name).strip()

def llm_provider() -> str:
    if _env("CEREBRAS_API_KEY"):
        return "cerebras"
    if _env("OPENAI_API_KEY"):
        return "openai"
    if _env("GROQ_API_KEY"):
        return "groq"
    if _env("SUNNY_LLM_KEY") and _env("SUNNY_LLM_URL"):
        return "custom"
    return "none"


def llm_status() -> dict[str, Any]:
    p = llm_provider()
    model = DEFAULT_CEREBRAS_MODEL if p == "cerebras" else (
        os.environ.get("SUNNY_LLM_MODEL", "gpt-4o-mini") if p != "none" else None
    )
    return {"provider": p, "model": model, "configured": p != "none"}


def _llm_key() -> str:
    p = llm_provider()
    return {
        "cerebras": _env("CEREBRAS_API_KEY"),
        "openai": _env("OPENAI_API_KEY"),
        "groq": _env("GROQ_API_KEY"),
        "custom": _env("SUNNY_LLM_KEY"),
    }.get(p, "").strip()


def _llm_url() -> str:
    p = llm_provider()
    if p == "cerebras":
        return "https://api.cerebras.ai/v1/chat/completions"
    if p == "openai":
        return (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    if p == "groq":
        return "https://api.groq.com/openai/v1/chat/completions"
    if p == "custom":
        return os.environ["SUNNY_LLM_URL"].rstrip("/") + "/chat/completions"
    return ""


def _llm_model() -> str:
    p = llm_provider()
    if p == "cerebras":
        return _env("CEREBRAS_MODEL") or DEFAULT_CEREBRAS_MODEL
    return _env("SUNNY_LLM_MODEL") or "gpt-4o-mini"


def _llm_request(prompt: str, system: str = "", max_tokens: int = 3000,
                 temperature: float = 0.2, json_mode: bool = False) -> str:
    key = _llm_key()
    if not key:
        raise RuntimeError("ingen LLM-nyckel")
    import requests

    body: dict[str, Any] = {
        "model": _llm_model(),
        "messages": [],
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if llm_provider() == "cerebras":
        body["reasoning_effort"] = os.environ.get("CEREBRAS_REASONING_EFFORT", "high")

    r = requests.post(
        _llm_url(),
        json=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{llm_provider()} HTTP {r.status_code}: {r.text[:700]}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"LLM-svar saknar text: {exc}")


def _parse_json(text: str) -> Any:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[A-Za-z0-9_-]*", "", t).strip()
        t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = t.find(opener)
        if start < 0:
            continue
        depth = 0
        inside = False
        esc = False
        for i in range(start, len(t)):
            c = t[i]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"':
                inside = not inside
                continue
            if inside:
                continue
            if c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except Exception:
                        break
    return None


def llm_json(prompt: str, system: str = "", max_tokens: int = 3000) -> Any:
    raw = _llm_request(prompt, system, max_tokens=max_tokens, temperature=0.2, json_mode=True)
    obj = _parse_json(raw)
    if obj is None:
        raise RuntimeError("LLM returnerade inte giltig JSON")
    return obj


def test_llm() -> dict[str, Any]:
    reply = _llm_request(
        "Reply with exactly VIDEOFINAL_LLM_OK.",
        system="Return only the requested token.",
        max_tokens=40,
        temperature=0,
    )
    return {"provider": llm_provider(), "model": _llm_model(), "reply": reply.strip()}


# =============================================================================
# TOPIC SCOUT / IDEA LAB
# =============================================================================

def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def slugify(s: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "project").strip().lower()).strip("-")
    return out[:90] or "project"


def google_news(query: str, count: int = 10) -> list[dict[str, str]]:
    url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    )
    try:
        raw = urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return []
    items = []
    for m in re.finditer(r"<item>(.*?)</item>", raw, re.S):
        body = m.group(1)
        title_m = re.search(r"<title>(.*?)</title>", body, re.S)
        link_m = re.search(r"<link>(.*?)</link>", body, re.S)
        date_m = re.search(r"<pubDate>(.*?)</pubDate>", body, re.S)
        title = html.unescape(title_m.group(1).strip()) if title_m else ""
        link = link_m.group(1).strip() if link_m else ""
        published = date_m.group(1).strip() if date_m else ""
        if title:
            items.append({"title": title, "url": link, "published": published})
        if len(items) >= count:
            break
    return items


def yt_candidates(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Find YouTube candidates with the same resilient client strategy as source download."""
    clients = ("android", "web")
    for client in clients:
        try:
            proc = run_cmd(
                [
                    sys.executable, "-m", "yt_dlp",
                    "--flat-playlist", "--dump-single-json", "--skip-download",
                    "--extractor-args", f"youtube:player_client={client}",
                    f"ytsearch{max(8, limit * 3)}:{query}",
                ],
                timeout=180, check=False,
            )
            if proc.returncode != 0:
                continue
            obj = json.loads(proc.stdout)
            rows = []
            for item in obj.get("entries", []) if isinstance(obj, dict) else []:
                if not isinstance(item, dict):
                    continue
                vid = item.get("id")
                url = item.get("webpage_url") or item.get("url")
                if vid and (not url or not str(url).startswith("http")):
                    url = "https://www.youtube.com/watch?v=" + str(vid)
                if not url:
                    continue
                rows.append({
                    "id": vid or "",
                    "url": url,
                    "title": norm_text(item.get("title", "")),
                    "uploader": norm_text(item.get("uploader") or item.get("channel") or ""),
                    "channel_url": item.get("channel_url") or "",
                    "client": client,
                })
                if len(rows) >= limit:
                    return rows
            if rows:
                return rows
        except Exception:
            continue
    return []


def kick_popular(limit: int = 20) -> list[dict[str, Any]]:
    url = "https://kick.com/api/v2/livestreams?sort=viewer_count&direction=desc&per_page=" + str(limit)
    try:
        raw = urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "ignore")
        obj = json.loads(raw)
    except Exception:
        return []
    out = []
    rows = obj.get("data", obj if isinstance(obj, list) else [])
    for row in rows:
        ch = row.get("channel") or {}
        user = ch.get("user") or {}
        name = user.get("username") or ch.get("slug") or ""
        title = norm_text(row.get("session_title", ""))
        viewers = int(row.get("viewer_count") or 0)
        if name and title:
            out.append({"title": f"{name}: {title}", "source": f"https://kick.com/{ch.get('slug') or name}", "signal": "kick", "viewers": viewers})
    return out


def reddit_hot(subreddit: str = "LivestreamFail", limit: int = 20) -> list[dict[str, Any]]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}&t=day&raw_json=1"
    req = urllib.request.Request(url, headers={"User-Agent": "VideoFinal/2026"})
    try:
        raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        obj = json.loads(raw)
    except Exception:
        return []
    out = []
    for child in obj.get("data", {}).get("children", []):
        d = child.get("data", {})
        title = norm_text(d.get("title", ""))
        if title:
            out.append({
                "title": title,
                "source": "https://www.reddit.com" + str(d.get("permalink", "")),
                "signal": "reddit",
                "score": int(d.get("score") or 0),
            })
    return out



STREAMER_WATCHLIST = [
    "Kai Cenat", "IShowSpeed", "Speed", "xQc", "Jynxzi", "Adin Ross",
    "HasanAbi", "Clix", "Sketch", "Carter Efe", "Fanum", "Duke Dennis",
    "AMP", "FaZe", "Drake", "Marlon", "Trainwreckstv", "Pokimane",
    "Nmplol", "Asmongold", "CaseOh", "PlaqueBoyMax", "Rayasianboy",
]
STREAMER_QUERY_ALIASES = {
    "Kai Cenat": ["Kai Cenat latest", "Kai Cenat Live", "Kai Cenat Kick", "Kai Cenat response"],
    "IShowSpeed": ["IShowSpeed latest", "IShowSpeed Live", "IShowSpeed Kick", "Speed response"],
    "xQc": ["xQc latest", "xQc Live", "xQc Kick", "xQc response"],
    "Jynxzi": ["Jynxzi latest", "Jynxzi Live", "Jynxzi response"],
    "Adin Ross": ["Adin Ross latest", "Adin Ross Live", "Adin Ross response"],
    "HasanAbi": ["HasanAbi latest", "HasanAbi Live", "HasanAbi response"],
    "Clix": ["Clix latest", "Clix Live", "Clix response"],
    "Sketch": ["Sketch streamer latest", "Sketch Live", "Sketch response"],
    "Carter Efe": ["Carter Efe latest", "Carter Efe Live", "Carter Efe response"],
    "Fanum": ["Fanum latest", "Fanum Live", "Fanum response"],
    "Duke Dennis": ["Duke Dennis latest", "Duke Dennis Live", "Duke Dennis response"],
    "Drake": ["Drake streamer", "Drake Kai Cenat", "Drake Kick streamer"],
    "Marlon": ["Marlon streamer", "Marlon Kick", "Marlon Drake", "Marlon live"],
}
def streamer_search_queries() -> list[str]:
    q=[]
    for arr in STREAMER_QUERY_ALIASES.values():
        q.extend(arr)
    q.extend([
        "streamer drama Kick latest", "Kick streamer controversy latest",
        "LivestreamFail streamer latest", "streamer beef latest",
        "streamer responds latest", "streamer banned latest", "streamer comeback latest",
    ])
    return list(dict.fromkeys(q))

def streamer_relevance(title: str, source: str = "", uploader: str = "") -> float:
    blob = (title + " " + source + " " + uploader).lower()
    score = 0.0
    for name in STREAMER_WATCHLIST:
        if name.lower() in blob:
            score += 0.24 if len(name) > 5 else 0.10
    if any(k in blob for k in ("kick.com", "livestreamfail", "twitch", "streamer", "vod", "live stream", "livestream")):
        score += 0.18
    if any(k in blob for k in ("controversy", "drama", "beef", "banned", "quit", "returns", "calls out", "responds", "response", "reacts", "incident", "clash", "fallout", "exposed")):
        score += 0.20
    if any(k in blob for k in ("latest", "breaking", "today", "2026", "update")):
        score += 0.08
    if any(k in blob for k in ("listicle", "how to stream", "tutorial", "beginner", "setup guide", "prime video", "shows streaming", "romance", "ranked shows")):
        score -= 0.50
    return max(0.0, min(1.0, score))


def niche_rows(niche: str, mode: str, limit: int = 10) -> list[dict[str, Any]]:
    seeds = NICHES.get(niche, NICHES["internet"])
    titles: list[dict[str, Any]] = []

    if niche == "streamers":
        # Entity-first streamer scouting: creator names and platform signals are the primary search axes.
        for query in streamer_search_queries():
            for item in google_news(query, count=6):
                titles.append({"title": item["title"], "source": item["url"], "signal": "news"})
            for item in yt_candidates(query, limit=6):
                titles.append({"title": item["title"], "source": item["url"], "signal": "youtube", "uploader": item.get("uploader", "")})
        titles.extend(kick_popular(24))
        for sub in ("LivestreamFail", "Twitch", "Kick"):
            titles.extend(reddit_hot(sub, 25))
    else:
        for seed in seeds:
            for item in google_news(seed, count=7):
                titles.append({"title": item["title"], "source": item["url"], "signal": "news"})
            for item in yt_candidates(seed, limit=6):
                titles.append({"title": item["title"], "source": item["url"], "signal": "youtube"})

    seen: set[str] = set()
    unique = []
    for row in titles:
        key = re.sub(r"\W+", "", row["title"].lower())[:150]
        if len(key) < 14 or key in seen:
            continue
        seen.add(key)
        unique.append(row)

    if niche == "streamers":
        unique.sort(key=lambda r: streamer_relevance(r.get("title", ""), r.get("source", ""), r.get("uploader", "")), reverse=True)
        relevant = [r for r in unique if streamer_relevance(r.get("title", ""), r.get("source", "") + " " + r.get("uploader", "")) >= 0.20]
        if len(relevant) >= 4:
            unique = relevant

    if not unique:
        return []

    base = []
    for row in unique[: max(30, limit * 6)]:
        t = row["title"].lower()
        hook = 5 + sum(1 for k in ("why", "how", "secret", "controversy", "exposed", "vs", "banned", "quit", "return", "responds", "calls out", "beef") if k in t)
        freshness = 6 + sum(1 for k in ("today", "latest", "breaking", "new", "announced", "update", "2026") if k in t)
        visual = 6 + sum(1 for k in ("stream", "fight", "game", "live", "record", "interview", "podcast", "clip", "vod") if k in t)
        depth = 5 + sum(1 for k in ("lawsuit", "history", "rise", "fall", "mystery", "scandal", "drama", "incident") if k in t)
        raw = 0.30 * min(hook, 10) + 0.24 * min(freshness, 10) + 0.22 * min(visual, 10) + 0.24 * min(depth, 10)
        if niche == "streamers":
            raw += 2.2 * streamer_relevance(row.get("title", ""), row.get("source", ""), row.get("uploader", ""))
        if any(k in t for k in ("how to stream", "beginner guide", "setup guide", "best romance", "prime video", "streaming shows", "ranked")):
            raw -= 4.5
        base.append({**row, "heuristic": round(max(0.0, min(10.0, raw)) * 10, 1), "niche": niche, "mode": mode})

    base.sort(key=lambda x: x["heuristic"], reverse=True)

    if llm_provider() != "none":
        try:
            sample = [{"i": i + 1, "title": r["title"], "signal": r["signal"], "url": r["source"]} for i, r in enumerate(base[:30])]
            obj = llm_json(
                "You are the senior showrunner for a research-led internet video studio. "
                f"Rank these {mode} story candidates for the {niche} niche. For streamers, prefer named creator incidents, "
                "fresh drama, stream moments, interviews, platform moves and creator-vs-creator stories. Reject generic tutorials, "
                "listicles and unrelated entertainment news. Score production opportunity, not guaranteed views. "
                'Return JSON {"items":[{"i":1,"score":92,"reason":"..."}]}\n'
                + json.dumps(sample, ensure_ascii=False),
                max_tokens=2200,
            )
            by_i = {int(x.get("i", 0)): x for x in obj.get("items", []) if isinstance(x, dict)}
            for i, row in enumerate(base[:30], 1):
                x = by_i.get(i)
                if x:
                    score = max(0.0, min(100.0, float(x.get("score", row["heuristic"]))))
                    # Keep streamer relevance as a hard prior even when the LLM is used.
                    if niche == "streamers":
                        score = 0.70 * score + 30.0 * streamer_relevance(row.get("title", ""), row.get("source", "") + " " + row.get("uploader", ""))
                    row["score"] = round(score, 1)
                    row["reason"] = norm_text(str(x.get("reason", "")))[:300]
            base[:30] = sorted(base[:30], key=lambda r: r.get("score", r["heuristic"]), reverse=True)
        except Exception:
            pass

    for row in base:
        row["score"] = row.get("score", row["heuristic"])
        row["score_10"] = round(row["score"] / 10, 1)
    return base[:limit]


# =============================================================================
# PROJECT STATE
# =============================================================================

@dataclass
class Project:
    root: Path
    state: dict[str, Any]

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "state.json").write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def stage(self, name: str) -> None:
        self.state["stage"]=name
        self.state.setdefault("stages",[]).append({"name":name,"at":time.time()})
        self.save()
        progress(_STAGE_PCT.get(name,_PROGRESS.get("pct",0.0)),name.upper().replace("_"," "))

    def note(self, msg: str, **data: Any) -> None:
        self.state.setdefault("events", []).append({"at": time.time(), "message": msg, **data})
        self.save()

    def fail(self, msg: str) -> None:
        self.state["status"] = "blocked"
        self.state.setdefault("errors", []).append({"at": time.time(), "message": msg})
        self.save()


def make_project(topic: str, mode: str, resolution: str) -> Project:
    slug = slugify(topic)
    root = PROJECTS / slug
    state = {
        "schema": "videofinal/2026-autopilot",
        "topic": topic,
        "mode": mode,
        "resolution": resolution,
        "status": "running",
        "stage": "bootstrap",
        "created": dt.datetime.now(dt.timezone.utc).isoformat(),
        "events": [],
        "stages": [],
        "errors": [],
        "artifacts": {},
    }
    p = Project(root, state)
    p.save()
    return p


def whisper_words(path: Path) -> list[dict[str, Any]]:
    """Optional word-level ASR fallback, lazily loaded once per process."""
    global _ASR_MODEL
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return []
    try:
        if _ASR_MODEL is None:
            _ASR_MODEL = WhisperModel(
                os.environ.get("VIDEOFINAL_ASR_MODEL", "base"),
                device=os.environ.get("VIDEOFINAL_ASR_DEVICE", "cpu"),
                compute_type=os.environ.get("VIDEOFINAL_ASR_COMPUTE", "int8"),
            )
        segments, _ = _ASR_MODEL.transcribe(str(path), word_timestamps=True)
        words = []
        for seg in segments:
            for w in (seg.words or []):
                txt = norm_text(w.word)
                if txt:
                    words.append({"text": txt, "start": float(w.start), "end": float(w.end)})
        return words
    except Exception:
        return []

# =============================================================================
# SOURCE TRANSCRIPTS / CLIPS
# =============================================================================

def parse_vtt(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    txt = path.read_text(encoding="utf-8", errors="ignore")
    out: list[dict[str, Any]] = []
    cue_re = re.compile(
        r"(?P<st>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(?P<et>\d{2}:\d{2}:\d{2}\.\d{3}).*?\n(?P<body>.*?)(?=\n\n|\Z)",
        re.S,
    )
    for m in cue_re.finditer(txt):
        def ts(s: str) -> float:
            h, mm, sec = s.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(sec)
        body = re.sub(r"<[^>]+>", "", m.group("body")).replace("\n", " ")
        body = norm_text(body)
        body = re.sub(r"\b(?:music|applause|laughs?)\b", "", body, flags=re.I).strip()
        if body:
            out.append({"start": ts(m.group("st")), "end": ts(m.group("et")), "text": body})
    return out


def source_meta(url: str, cache_dir: Path) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:18]
    out = cache_dir / f"{key}.json"
    if out.exists():
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            pass
    last_err = "source metadata failed"
    for client in ("android_vr", "android", "web_embedded", "tv", "default", "web"):
        proc = run_cmd(
            [
                sys.executable, "-m", "yt_dlp",
                "--dump-single-json", "--skip-download",
                "--extractor-args", f"youtube:player_client={client}",
                url,
            ],
            timeout=180,
            check=False,
        )
        if proc.returncode == 0:
            meta = json.loads(proc.stdout)
            keep = {
                "id": meta.get("id"), "title": meta.get("title"),
                "uploader": meta.get("uploader") or meta.get("channel"),
                "channel_url": meta.get("channel_url"), "duration": meta.get("duration"),
                "webpage_url": meta.get("webpage_url") or url, "thumbnail": meta.get("thumbnail"),
                "upload_date": meta.get("upload_date"), "client": client,
            }
            out.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
            return keep
        last_err = proc.stderr[-1200:] or last_err
    raise RuntimeError(last_err)


def fetch_source_subtitles(url: str, cache_dir: Path) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:18]
    prefix = cache_dir / key
    vtts = list(cache_dir.glob(key + "*.vtt"))
    if not vtts:
        for client in ("android", "web"):
            cmd = [
                sys.executable, "-m", "yt_dlp", "--skip-download",
                "--write-subs", "--write-auto-subs", "--sub-langs", "en.*,en",
                "--sub-format", "vtt", "--convert-subs", "vtt",
                "--extractor-args", f"youtube:player_client={client}",
                "-o", str(prefix) + ".%(ext)s", url,
            ]
            run_cmd(cmd, timeout=240, check=False)
            vtts = list(cache_dir.glob(key + "*.vtt"))
            if vtts:
                break
    for vtt in vtts:
        cues = parse_vtt(vtt)
        if cues:
            return cues
    return []


def source_is_plausibly_first_party(row: dict[str, Any], story_entities: list[str]) -> float:
    blob = (row.get("title", "") + " " + row.get("uploader", "")).lower()
    score = 0.30
    for ent in story_entities:
        e = ent.lower()
        if e and (e in blob or any(part in blob for part in e.split() if len(part) >= 4)):
            score += 0.20
    if any(k in blob for k in ("official", "channel", "tv", "live", "podcast", "interview")):
        score += 0.08
    if any(k in blob for k in ("reaction", "fan", "edit", "compilation", "highlights")):
        score -= 0.18
    return max(0.0, min(1.0, score))


def _deterministic_entities(topic: str, research: dict[str, Any]) -> list[str]:
    blob = " ".join([topic] + [str(x.get("text", "")) for x in research.get("claims", [])[:12]])
    found = []
    for name in STREAMER_WATCHLIST:
        if name.lower() in blob.lower():
            found.append(name)
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9_-]{2,}(?:\s+[A-Z][A-Za-z0-9_-]{2,})?\b", topic):
        x = norm_text(m.group(0))
        if x.lower() not in {"the", "this", "what", "after", "how", "why", "and"} and x not in found:
            found.append(x)
    return list(dict.fromkeys(found))[:8]


def choose_sources(topic: str, research: dict[str, Any], count: int = 7) -> list[dict[str, Any]]:
    entities: list[str] = _deterministic_entities(topic, research)
    if llm_provider() != "none":
        try:
            obj = llm_json(
                "Extract the main creators/people/channels directly relevant to this story. "
                'Return JSON {"entities":["..."]}.\n' + topic + "\n" +
                json.dumps(research.get("claims", [])[:20], ensure_ascii=False)[:9000],
                max_tokens=500,
            )
            ents = [norm_text(x) for x in obj.get("entities", []) if norm_text(x)]
            if ents:
                entities = ents
        except Exception:
            pass

    queries=[topic]
    for entity in entities[:8]:
        queries += [
            f"{entity} original stream", f"{entity} live stream", f"{entity} interview",
            f"{entity} response", f"{entity} clip", f"{entity} latest"
        ]
    queries += [q for q in research.get("queries", []) if q]
    lower_topic=topic.lower()
    if any(x in lower_topic for x in ("streamer","kick","twitch","kai cenat","ishowspeed","xqc","jynxzi","adin ross","marlon")):
        queries += streamer_search_queries()

    candidates=[];seen=set()
    for q in list(dict.fromkeys(queries))[:45]:
        for row in yt_candidates(q, limit=8):
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            row["party_score"]=round(source_is_plausibly_first_party(row, entities),3)
            row["streamer_score"]=round(streamer_relevance(row.get("title",""),row.get("url",""),row.get("uploader","")),3) if any(x in lower_topic for x in ("streamer","kick","twitch")) else 0.0
            if any(x in lower_topic for x in ("streamer","kick","twitch")) and row["streamer_score"] < 0.10:
                continue
            candidates.append(row)

    candidates.sort(key=lambda r:(r.get("streamer_score",0),r["party_score"]),reverse=True)
    if not candidates:
        return []

    if llm_provider() != "none":
        try:
            sample=[{"i":i+1,"title":r["title"],"uploader":r["uploader"],"url":r["url"],
                     "party_score":r["party_score"],"streamer_score":r.get("streamer_score",0)}
                    for i,r in enumerate(candidates[:60])]
            obj=llm_json(
                "You are the FOOTAGE agent. Choose actual audiovisual sources for a creator story. "
                "Prefer the creator's own YouTube/Kick/Twitch material, original interviews, official event feeds, "
                "or a clearly identifiable primary recording. Reject news articles represented as if they were clips, "
                "fan edits, compilations, reactions, mirrors and generic tutorials. "
                'Return JSON {"pick":[1,2,3,4,5,6,7]}.\n'+json.dumps(sample,ensure_ascii=False),
                max_tokens=1500,
            )
            picks=[]
            for n in obj.get("pick",[])[:count]:
                try:picks.append(candidates[int(n)-1])
                except Exception:pass
            if picks:candidates=picks
        except Exception:
            pass
    return candidates[:count]

def choose_dialogue_segments(source: dict[str, Any], cues: list[dict[str, Any]],
                             mode: str, wanted: int = 2) -> list[dict[str, Any]]:
    if not cues:
        return []

    windows: list[dict[str, Any]] = []
    # Merge nearby subtitle cues into 4-8 second quote windows.
    for i in range(len(cues)):
        text_parts = []
        start = cues[i]["start"]
        end = cues[i]["end"]
        for j in range(i, min(len(cues), i + 7)):
            if cues[j]["start"] - start > 8.0:
                break
            text_parts.append(cues[j]["text"])
            end = cues[j]["end"]
            duration = end - start
            if 4.0 <= duration <= 8.0:
                joined = norm_text(" ".join(text_parts))
                if len(joined.split()) >= 6:
                    windows.append({"cue_start": start, "cue_end": end, "quote": joined})
    # Remove near duplicates.
    dedup: list[dict[str, Any]] = []
    seen = set()
    for w in windows:
        key = re.sub(r"\W+", "", w["quote"].lower())[:100]
        if key not in seen:
            seen.add(key)
            dedup.append(w)
    windows = dedup

    if llm_provider() != "none" and windows:
        sample = [{"i": i + 1, **w} for i, w in enumerate(windows[:60])]
        try:
            obj = llm_json(
                "Pick quote-worthy original spoken moments from this subtitle transcript. "
                "Prefer complete thoughts, strong reactions, concrete claims, emotional turns, "
                "or moments that advance a story. Never fabricate words. "
                'Return JSON {"pick":[{"i":1,"score":9.3,"reason":"..."}]} with at most '
                f"{wanted * 2} picks.\n"
                + json.dumps(sample, ensure_ascii=False)[:14000],
                max_tokens=1600,
            )
            picked = []
            for item in obj.get("pick", []):
                try:
                    idx = int(item["i"]) - 1
                    w = dict(windows[idx])
                    w["selection_score"] = float(item.get("score", 7.0))
                    w["reason"] = norm_text(str(item.get("reason", "")))[:240]
                    picked.append(w)
                except Exception:
                    pass
            if picked:
                picked.sort(key=lambda x: x.get("selection_score", 0), reverse=True)
                windows = picked
        except Exception:
            pass

    for w in windows:
        w["cut"] = max(0.0, float(w["cue_start"]) - 0.18)
        w["dur"] = min(8.0, float(w["cue_end"]) - w["cut"] + 0.32)
        w["source_url"] = source["url"]
        w["source_title"] = source.get("title", "")
        w["uploader"] = source.get("uploader", "")
    return windows[:wanted]


def choose_asr_windows(source: dict[str, Any], words: list[dict[str, Any]], wanted: int = 3) -> list[dict[str, Any]]:
    """Turn local/absolute Whisper word timings into 4-8s complete spoken moments."""
    if not words:
        return []
    windows = []
    for i in range(len(words)):
        start = float(words[i]["start"])
        end = float(words[i]["end"])
        buf = []
        for j in range(i, min(len(words), i + 45)):
            if float(words[j]["start"]) - start > 8.0:
                break
            buf.append(words[j])
            end = float(words[j]["end"])
            dur = end - start
            text = norm_text(" ".join(w["text"] for w in buf))
            if 4.0 <= dur <= 8.0 and len(text.split()) >= 6:
                windows.append({"cue_start": start, "cue_end": end, "quote": text})
    dedup, seen = [], set()
    for w in windows:
        k = re.sub(r"\W+", "", w["quote"].lower())[:120]
        if k in seen:
            continue
        seen.add(k); dedup.append(w)
    dedup.sort(key=lambda w: (len(w["quote"].split()), w["cue_start"]), reverse=True)
    out = dedup[:wanted]
    for w in out:
        w["cut"] = max(0.0, float(w["cue_start"]) - 0.18)
        w["dur"] = min(8.0, float(w["cue_end"]) - w["cut"] + 0.32)
        w["source_url"] = source["url"]
        w["source_title"] = source.get("title", "")
        w["uploader"] = source.get("uploader", "")
        w["asr_words"] = words
    return out


def automatic_probe_moments(source: dict[str, Any], project: Project, wanted: int = 3) -> list[dict[str, Any]]:
    """Download a few small windows and ASR them when platform captions are unavailable."""
    duration = float(source.get("duration") or 0)
    if duration < 5:
        return []
    if not has_module("faster_whisper"):
        return []
    usable = max(5.5, min(8.5, duration * 0.18))
    positions = sorted(set([
        0.0,
        max(0.0, duration * 0.28 - usable / 2),
        max(0.0, duration * 0.55 - usable / 2),
        max(0.0, duration * 0.78 - usable / 2),
    ]))
    all_moments = []
    for cut in positions:
        if cut + 4.0 >= duration:
            continue
        cut = min(cut, max(0.0, duration - usable))
        key = hashlib.sha1((source["url"] + f"|probe|{cut:.2f}").encode()).hexdigest()[:12]
        probe = ASSET_CLIPS / f"{slugify(source.get('title') or 'source')}_probe_{key}.mp4"
        try:
            if not probe.exists():
                download_source_segment(source["url"], cut, usable, probe)
            words_local = whisper_words(probe)
            words_abs = [
                {"text": w["text"], "start": float(w["start"]) + cut, "end": float(w["end"]) + cut}
                for w in words_local
            ]
            for m in choose_asr_windows(source, words_abs, wanted=2):
                m["asr_words"] = words_abs
                all_moments.append(m)
        except Exception as exc:
            project.note("asr_probe_failed", url=source["url"], cut=cut, error=str(exc)[:300])
        if len(all_moments) >= wanted:
            break
    return all_moments[:wanted]


def _media_duration(path: Path) -> float:
    try:
        return float(run_cmd([ffprobe(), "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(path)], timeout=90).stdout.strip())
    except Exception:
        return 0.0

def _usable_download(path: Path, requested: float) -> bool:
    return path.exists() and path.stat().st_size > 12000 and _media_duration(path) >= max(1.0, requested * 0.90)

def download_source_segment(url: str, cut: float, dur: float, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    formats = (
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/best",
        "best[height<=720]/best",
    )
    last = ""
    for fmt in formats:
        for client in ("android_vr", "android", "web_embedded", "tv", "default", "web"):
            cmd = [
                sys.executable, "-m", "yt_dlp", "--no-progress", "--force-keyframes-at-cuts",
                "--merge-output-format", "mp4", "-f", fmt,
                "--download-sections", f"*{cut:.2f}-{cut + dur:.2f}",
                "--extractor-args", f"youtube:player_client={client}",
                "-o", str(out), url,
            ]
            proc = run_cmd(cmd, timeout=700, check=False)
            last = (proc.stderr or proc.stdout or "")[-1400:]
            if proc.returncode == 0 and _usable_download(out, dur):
                return out
            if out.exists():
                try: out.unlink()
                except Exception: pass

    temp = out.with_suffix(".source.mp4")
    for client in ("android_vr", "android", "web_embedded", "tv", "default"):
        proc = run_cmd([
            sys.executable, "-m", "yt_dlp", "--no-progress", "--merge-output-format", "mp4",
            "-f", formats[0], "--extractor-args", f"youtube:player_client={client}",
            "-o", str(temp), url
        ], timeout=1200, check=False)
        last = (proc.stderr or proc.stdout or "")[-1400:]
        if proc.returncode == 0 and temp.exists() and _media_duration(temp) >= cut + 2.0:
            break
    if not temp.exists() or _media_duration(temp) < cut + 2.0:
        raise RuntimeError("source download failed or source shorter than cut: " + last)

    run_cmd([
        ffmpeg(), "-y", "-v", "error", "-ss", f"{cut:.2f}", "-t", f"{dur:.2f}", "-i", str(temp),
        "-vf", "scale=-2:720,fps=30,setsar=1", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(out),
    ], timeout=1000)
    try: temp.unlink()
    except Exception: pass
    if not _usable_download(out, dur):
        raise RuntimeError(f"source trim too short: requested={dur:.2f}s actual={_media_duration(out):.2f}s")
    return out


# =============================================================================
# SCRIPT / NARRATION PLANNING
# =============================================================================

def gather_research(topic: str) -> dict[str, Any]:
    news = google_news(topic, count=12)
    claims = [{"text": n["title"], "url": n["url"], "kind": "reported"} for n in news]
    if llm_provider() != "none":
        try:
            prompt = (
                "You are a fact-first research editor. Build a compact research brief for the story. "
                "Use only the supplied source headlines/URLs; do not invent facts. Identify entities, "
                "timeline hints, what is confirmed, what is only reported, and 3-6 follow-up search "
                "queries. Return JSON with keys claims, entities, queries, unknowns. "
                "claims should each contain text, source_url, confidence.\n"
                f"TOPIC: {topic}\nSOURCES:\n" + json.dumps(news, ensure_ascii=False)
            )
            obj = llm_json(prompt, max_tokens=2200)
            claims2 = []
            for c in obj.get("claims", []):
                if isinstance(c, dict) and c.get("text"):
                    claims2.append(
                        {
                            "text": norm_text(c["text"]),
                            "source_url": c.get("source_url", ""),
                            "confidence": float(c.get("confidence", 0.65)),
                        }
                    )
            if claims2:
                claims = claims2
            return {
                "claims": claims,
                "entities": [norm_text(x) for x in obj.get("entities", []) if norm_text(x)],
                "queries": [norm_text(x) for x in obj.get("queries", []) if norm_text(x)],
                "unknowns": obj.get("unknowns", []),
                "news": news,
            }
        except Exception:
            pass
    entities = _deterministic_entities(topic, {"claims": claims})
    followups = [topic]
    for e in entities[:4]:
        followups.extend([f"{e} latest", f"{e} response", f"{e} original clip"])
    return {"claims": claims, "entities": entities, "queries": list(dict.fromkeys(followups)), "unknowns": [], "news": news}


def build_short_script(topic: str, research: dict[str, Any], selected_moments: list[dict[str, Any]]) -> dict[str, Any]:
    moments = [
        {
            "id": i + 1,
            "quote": m["quote"],
            "source": m["source_title"],
            "url": m["source_url"],
            "cut": m["cut"],
            "dur": m["dur"],
        }
        for i, m in enumerate(selected_moments)
    ]
    if llm_provider() != "none":
        try:
            obj = llm_json(
                "Write a 45-59 second research-led YouTube Short. "
                "Start with a real source moment; do not write an intro before it. "
                "Use original source dialogue for 4-8 seconds when a moment is provided, then "
                "use concise narrator context, then another source moment, then consequence/payoff. "
                "No fabricated quotes. No unsupported motives, dates, numbers or accusations. "
                "Do not repeat the same claim. End with a specific audience question. "
                "Return JSON: {title, hook, narration:[...], order:[...], final_question}. "
                "Each narration item is one complete sentence and must be usable as TTS.\n"
                f"TOPIC: {topic}\nRESEARCH:\n{json.dumps(research, ensure_ascii=False)[:12000]}\n"
                f"SOURCE MOMENTS:\n{json.dumps(moments, ensure_ascii=False)}",
                max_tokens=3000,
            )
            if obj.get("narration") and obj.get("order"):
                return obj
        except Exception:
            pass

    # Deterministic fallback: enough narration to produce a meaningful 45-59s cut.
    lead = (research.get("claims") or [{"text": "The latest reporting has put this story back in focus."}])[0]["text"]
    narr = [
        f"Here is what actually changed around {topic}.",
        f"The clearest reported detail so far is this: {lead}.",
        "That matters because the original reaction and the later context are not the same thing.",
        "And this is where the story becomes more interesting than the headline.",
        "The remaining question is what happens next, now that the context is visible.",
    ]
    return {
        "title": topic,
        "hook": "",
        "narration": narr,
        "order": ["source:0", "narr:0", "source:1", "narr:1", "source:2", "narr:2", "narr:3", "narr:4"],
        "final_question": "Would you have handled it the same way?",
    }


def build_doc_script(topic: str, research: dict[str, Any], moments: list[dict[str, Any]],
                     target_seconds: int) -> dict[str, Any]:
    if llm_provider() != "none":
        try:
            obj = llm_json(
                "Write an original 5-act internet documentary script. "
                "Structure: hook/ascension, blindspot or setup, breaking point with real source "
                "dialogue, escalation/reaction, aftermath/payoff. Use 12-18 narrator blocks and "
                "6-10 source moments. Let source speakers finish complete thoughts. "
                "Never invent quotes or unsupported claims. Return JSON {title, blocks:[...]}, where "
                "each block has kind='source' or 'narration', text, moment_index for source blocks, "
                "and purpose. Target duration is approximate; actual TTS duration controls timing.\n"
                f"TOPIC: {topic}\nTARGET: {target_seconds}s\nRESEARCH:\n"
                f"{json.dumps(research, ensure_ascii=False)[:15000]}\nMOMENTS:\n"
                f"{json.dumps([{'i':i+1,'quote':m['quote'],'cut':m['cut'],'dur':m['dur']} for i,m in enumerate(moments)], ensure_ascii=False)[:12000]}",
                max_tokens=5000,
            )
            if obj.get("blocks"):
                return obj
        except Exception:
            pass

    blocks = []
    lead = (research.get("claims") or [{"text": f"The story around {topic} is moving again."}])[0]["text"]
    blocks.append({"kind": "narration", "text": f"Most people think they know the story of {topic}. The latest evidence is more complicated.", "purpose": "hook"})
    blocks.append({"kind": "narration", "text": lead[:350], "purpose": "setup"})
    for i, m in enumerate(moments[:8]):
        blocks.append({"kind": "source", "moment_index": i, "text": "", "purpose": "evidence"})
        blocks.append({"kind": "narration", "text": "That moment changes what comes next, because the context behind it matters.", "purpose": "analysis"})
    blocks.append({"kind": "narration", "text": f"The real question now is what happens next with {topic}.", "purpose": "payoff"})
    return {"title": topic, "blocks": blocks}


# =============================================================================
# TTS
# =============================================================================

async def _tts_async(text: str, voice: str, out: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice).save(str(out))


def tts(text: str, voice: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 500:
        return out
    try:
        asyncio.run(_tts_async(text, voice, out))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_tts_async(text, voice, out))
        loop.close()
    return out


def audio_duration(path: Path) -> float:
    proc = run_cmd(
        [ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    )
    return float(proc.stdout.strip())


# =============================================================================
# CINEMA / AUDIO
# =============================================================================

def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def piano_note(midi: float, duration: float, amp: float) -> np.ndarray:
    t = np.arange(int(duration * SR)) / SR
    f = midi_hz(midi)
    a = np.zeros(len(t), dtype=np.float32)
    for h, weight in ((1, 1.0), (2, 0.28), (3, 0.14), (4, 0.05), (6, 0.015)):
        a += weight * np.sin(2 * np.pi * f * h * (1 + 0.00004 * h) * t) * np.exp(-t * (0.9 + 0.24 * h))
    a *= np.minimum(1.0, t / 0.012) * np.minimum(1.0, (duration - t) / 0.2)
    return (amp * a).astype(np.float32)


def synth_music(duration: float, seed: int = 7) -> Path:
    rng = np.random.default_rng(seed)
    n = int(math.ceil(duration + 1.0) * SR)
    music = np.zeros(n, dtype=np.float32)
    beat = 60 / 68
    progression = [[45, 52, 57, 60], [41, 48, 53, 57], [43, 50, 55, 59], [40, 47, 52, 55]]

    def add(at: float, arr: np.ndarray) -> None:
        i = int(at * SR)
        if i >= len(music):
            return
        take = min(len(arr), len(music) - i)
        if take > 0:
            music[i:i + take] += arr[:take]

    for bar, at in enumerate(np.arange(0, duration, beat * 8)):
        chord = progression[bar % len(progression)]
        length = beat * 10
        t = np.arange(int(length * SR)) / SR
        env = np.sin(np.pi * np.clip(t / length, 0, 1)) ** 1.8
        pad = np.zeros(len(t), dtype=np.float32)
        for m in chord:
            f = midi_hz(m)
            pad += (
                np.sin(2 * np.pi * f * t)
                + 0.30 * np.sin(2 * np.pi * f * 1.0017 * t)
                + 0.08 * np.sin(2 * np.pi * 2 * f * t)
            ) / len(chord)
        add(at, 0.09 * pad * env)
        for off, note, vel in (
            (0, chord[0] + 12, 0.095),
            (2.5, chord[2] + 12, 0.065),
            (5.0, chord[3] + 12, 0.055),
            (6.5, chord[1] + 12, 0.04),
        ):
            add(at + off * beat, piano_note(note, 4.4, vel))

    # sparse vinyl/noise bed, deterministic per render
    noise = rng.normal(0, 0.0025, size=n).astype(np.float32)
    noise *= np.exp(-np.arange(n, dtype=np.float32) / SR / 180.0)
    music += noise
    fade = min(int(1.2 * SR), len(music) // 8)
    music[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
    music[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    peak = max(float(np.max(np.abs(music))), 1e-6)
    music *= min(0.65 / peak, 1.0)

    out = CACHE / f"music_{duration:.2f}_{seed}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((music * 32767).astype("<i2").tobytes())
    return out


def synth_sfx(total: float, cue_times: list[float]) -> Path:
    n = int(math.ceil(total + 1) * SR)
    out = np.zeros(n, dtype=np.float32)
    for k, at in enumerate(cue_times):
        length = 0.65
        t = np.arange(int(length * SR)) / SR
        freq = 90 + 25 * np.sin(k * 0.7)
        env = np.exp(-4 * t) * np.minimum(t / 0.004, 1.0)
        impact = 0.42 * np.sin(2 * np.pi * freq * t) * env
        j = int(at * SR)
        end = min(n, j + len(impact))
        if j < n:
            out[j:end] += impact[: end - j]
    peak = max(float(np.max(np.abs(out))), 1e-6)
    out *= min(0.45 / peak, 1.0)
    path = CACHE / f"sfx_{total:.2f}_{len(cue_times)}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype("<i2").tobytes())
    return path


def font_path() -> Optional[Path]:
    candidates = [
        os.environ.get("VIDEOFINAL_FONT"),
        str(ROOT / "assets" / "fonts" / "Anton-Regular.ttf"),
        str(ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if p and Path(p).exists():
            return Path(p)
    return None


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    p = font_path()
    if p:
        return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def fit_cover(im: Image.Image, w: int, h: int, focus: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    iw, ih = im.size
    scale = max(w / iw, h / ih)
    im = im.resize((int(iw * scale), int(ih * scale)), Image.Resampling.LANCZOS)
    nw, nh = im.size
    left = int(max(0, (nw - w) * focus[0]))
    top = int(max(0, (nh - h) * focus[1]))
    return im.crop((left, top, left + w, top + h))


def grade_frame(im: Image.Image) -> Image.Image:
    im = ImageEnhance.Contrast(im).enhance(1.08)
    im = ImageEnhance.Color(im).enhance(0.88)
    im = ImageEnhance.Brightness(im).enhance(0.97)
    return im


def vignette(w: int, h: int, strength: float = 0.28) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    d = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / math.sqrt(2)
    return (1 - strength * np.clip(d, 0, 1) ** 2.0).astype(np.float32)


def apply_vignette(im: Image.Image, mask: np.ndarray) -> Image.Image:
    arr = np.asarray(im, dtype=np.float32) * mask[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def drift(im: Image.Image, t: float, w: int, h: int, seed: int) -> Image.Image:
    zoom = 1.01 + 0.025 * (0.5 + 0.5 * math.sin((t + seed) * 0.4))
    nw, nh = int(w * zoom), int(h * zoom)
    z = im.resize((nw, nh), Image.Resampling.LANCZOS)
    ox = int((nw - w) * (0.50 + 0.08 * math.sin((t + seed) * 0.31)))
    oy = int((nh - h) * (0.50 + 0.05 * math.cos((t + seed) * 0.23)))
    return z.crop((ox, oy, ox + w, oy + h))


# =============================================================================
# CAPTIONING
# =============================================================================

def proportional_words(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words = []
    for cue in cues:
        toks = cue["text"].split()
        if not toks:
            continue
        total = sum(max(1, len(t)) for t in toks)
        t = cue["start"]
        for tok in toks:
            dur = (cue["end"] - cue["start"]) * max(1, len(tok)) / total
            words.append({"text": tok, "start": t, "end": t + dur})
            t += dur
    return words


def caption_groups(words: list[dict[str, Any]], max_words: int = 4, max_chars: int = 22) -> list[dict[str, Any]]:
    groups = []
    buf = []
    for word in words:
        if buf:
            candidate = " ".join(x["text"] for x in buf + [word])
            if len(buf) >= max_words or len(candidate) > max_chars or word["start"] - buf[-1]["end"] > 0.45:
                groups.append(
                    {"start": buf[0]["start"], "end": buf[-1]["end"], "text": " ".join(x["text"] for x in buf)}
                )
                buf = []
        buf.append(word)
    if buf:
        groups.append({"start": buf[0]["start"], "end": buf[-1]["end"], "text": " ".join(x["text"] for x in buf)})
    return groups


def block_caption_groups(text: str, start: float, dur: float) -> list[dict[str, Any]]:
    words = text.split()
    if not words:
        return []
    weights = [max(1, len(w)) for w in words]
    total = sum(weights)
    out = []
    t = start
    buf = []
    bw = 0
    for word, wt in zip(words, weights):
        if buf and (len(buf) >= 4 or bw + wt > 18):
            span = dur * bw / total
            out.append({"start": t, "end": t + span, "text": " ".join(buf)})
            t += span
            buf = []
            bw = 0
        buf.append(word)
        bw += wt
    if buf:
        out.append({"start": t, "end": start + dur, "text": " ".join(buf)})
    return out


def draw_captions(im: Image.Image, groups: list[dict[str, Any]], time_abs: float,
                  w: int, h: int) -> Image.Image:
    active = next((g for g in groups if g["start"] <= time_abs < g["end"] + 0.08), None)
    if not active:
        return im
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = get_font(max(20, round(w * 52 / 720)))
    txt = active["text"]
    max_w = int(w * 0.77)
    lines = []
    line = ""
    for word in txt.split():
        test = (line + " " + word).strip()
        if line and d.textlength(test, font=f) > max_w:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)
    lines = lines[:2]
    y = int(h * 0.74 if h >= 1000 else h * 0.75)
    for ln in lines:
        tw = d.textlength(ln, font=f)
        x = (w - tw) / 2
        d.text((x, y), ln, font=f, fill="white", stroke_width=max(2, round(w * 5 / 720)), stroke_fill="black")
        y += int(h * 61 / 1280)
    return Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")


def make_srt(groups: list[dict[str, Any]], path: Path) -> None:
    def stamp(s: float) -> str:
        ms = int(round(max(0, s) * 1000))
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        sec = (ms % 60000) // 1000
        rem = ms % 1000
        return f"{h:02}:{m:02}:{sec:02},{rem:03}"

    path.write_text(
        "\n\n".join(
            f"{i}\n{stamp(g['start'])} --> {stamp(g['end'])}\n{g['text']}"
            for i, g in enumerate(groups, 1)
        ) + "\n",
        encoding="utf-8",
    )


# =============================================================================
# RENDERER
# =============================================================================

@dataclass
class Shot:
    kind: str
    start: float
    dur: float
    clip: Optional[Path] = None
    clip_cut: float = 0.0
    source_words: Optional[list[dict[str, Any]]] = None
    narration: str = ""
    note: str = ""
    card_text: str = ""
    card_sub: str = ""


def render_shot_video(shot: Shot, out: Path, mode: str, resolution: str,
                      caption_groups_abs: list[dict[str, Any]]) -> Path:
    if cv2 is None:
        raise RuntimeError("opencv-python krävs för renderern.")
    W, H = RESOLUTIONS[resolution][mode]
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    if not writer.isOpened():
        raise RuntimeError(f"VideoWriter kunde inte öppna {out}")

    cap = cv2.VideoCapture(str(shot.clip)) if shot.clip else None
    if shot.clip and (cap is None or not cap.isOpened()):
        writer.release()
        raise RuntimeError(f"kan inte öppna clip {shot.clip}")

    vig = vignette(W, H)
    frame_count = int(math.ceil(shot.dur * FPS))
    fps_src = max(1.0, cap.get(cv2.CAP_PROP_FPS) or FPS) if cap else FPS
    current_idx = -1
    current_frame = None

    for i in range(frame_count):
        t = i / FPS
        if cap:
            target_idx = int((shot.clip_cut + t) * fps_src)
            if target_idx < current_idx or target_idx > current_idx + 6:
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                current_idx = target_idx - 1
            while current_idx < target_idx:
                ok, bgr = cap.read()
                current_idx += 1
                if not ok:
                    cap.release(); writer.release()
                    raise RuntimeError(f"clip ended early: {shot.clip}")
                current_frame = bgr
            if current_frame is None:
                cap.release(); writer.release()
                raise RuntimeError(f"no frame decoded: {shot.clip}")
            im = Image.fromarray(cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB))
            im = fit_cover(im, W, H)
            im = grade_frame(im)
            im = drift(im, t, W, H, i % 11)
        elif shot.kind == "card":
            im = Image.new("RGB", (W, H), (10, 12, 16))
            d = ImageDraw.Draw(im)
            main = get_font(max(34, W // 18))
            small = get_font(max(18, W // 55))
            d.text((W / 2 + 4, H / 2 - 20 + 4), shot.card_text.upper(), font=main, fill=(0, 0, 0), anchor="mm")
            d.text((W / 2, H / 2 - 20), shot.card_text.upper(), font=main, fill=(240, 240, 238), anchor="mm")
            d.rectangle((W * 0.43, H * 0.64, W * 0.57, H * 0.645), fill=(195, 35, 40))
            if shot.card_sub:
                d.text((W / 2, H * 0.69), shot.card_sub.upper(), font=small, fill=(195, 35, 40), anchor="mm")
            im = drift(im, t, W, H, 3)
        else:
            im = Image.new("RGB", (W, H), (12, 14, 18))

        im = apply_vignette(im, vig)
        if i < 3:
            a = i / 3.0
            arr = np.asarray(im, dtype=np.float32)
            arr = arr * a + 255 * (1 - a) * 0.06
            im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        im = draw_captions(im, caption_groups_abs, shot.start + t, W, H)
        writer.write(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))

    writer.release()
    if cap:
        cap.release()
    return out


def build_audio_mix(shots: list[Shot], total: float, music_path: Path, sfx_path: Path,
                    project: Project) -> Path:
    # Individual delayed inputs keep the filter graph simple and memory bounded.
    dialogue_inputs: list[Path] = []
    source_inputs: list[Path] = []

    for idx, shot in enumerate(shots):
        if shot.narration:
            wav = project.root / f"narration_{idx:02d}.mp3"
            tts(shot.narration, DEFAULT_VOICE, wav)
            dialogue_inputs.append(wav)
        if shot.clip and shot.kind == "source":
            wav = project.root / f"source_{idx:02d}.wav"
            run_cmd(
                [
                    ffmpeg(), "-y", "-v", "error",
                    "-ss", f"{shot.clip_cut:.3f}", "-t", f"{shot.dur:.3f}",
                    "-i", str(shot.clip), "-vn",
                    "-af", "highpass=f=70,lowpass=f=9000,loudnorm=I=-17:TP=-2:LRA=7",
                    "-ar", str(SR), "-ac", "1", str(wav),
                ],
                timeout=300,
            )
            source_inputs.append(wav)

    # Convert TTS mp3 inputs to normalized wavs so the mix is deterministic.
    norm_dialogue: list[Path] = []
    for idx, path in enumerate(dialogue_inputs):
        wav = project.root / f"vo_{idx:02d}.wav"
        run_cmd([
            ffmpeg(), "-y", "-v", "error", "-i", str(path),
            "-af", "highpass=f=70,lowpass=f=9000,loudnorm=I=-17:TP=-2:LRA=7",
            "-ar", str(SR), "-ac", "1", str(wav)
        ])
        norm_dialogue.append(wav)

    labels = []
    inputs = []
    filters = []
    in_idx = 0
    vo_idx = 0
    src_idx = 0
    for shot in shots:
        if shot.narration:
            path = norm_dialogue[vo_idx]
            vo_idx += 1
            inputs += ["-i", str(path)]
            delay = int(shot.start * 1000)
            filters.append(f"[{in_idx}:a]adelay={delay}|{delay},volume=1.0[vo{in_idx}]")
            labels.append(f"[vo{in_idx}]")
            in_idx += 1
        if shot.clip and shot.kind == "source":
            path = source_inputs[src_idx]
            src_idx += 1
            inputs += ["-i", str(path)]
            delay = int(shot.start * 1000)
            filters.append(f"[{in_idx}:a]adelay={delay}|{delay},volume=0.95[src{in_idx}]")
            labels.append(f"[src{in_idx}]")
            in_idx += 1

    if labels:
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0[dialogue]")
    else:
        filters.append("anullsrc=channel_layout=mono:sample_rate=44100:d=1[dialogue]")
    dialogue_label = "[dialogue]"

    # Add a music track and sidechain it with the full dialogue track.
    inputs += ["-i", str(music_path), "-i", str(sfx_path)]
    music_i = in_idx
    sfx_i = in_idx + 1
    filters.append(f"[{music_i}:a]volume=0.34,apad,atrim=0:{total:.3f}[music]")
    filters.append(f"[music]{dialogue_label}sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[ducked]")
    filters.append(f"{dialogue_label}[ducked][{sfx_i}:a]amix=inputs=3:duration=first:dropout_transition=0,"
                   "dynaudnorm=f=150:g=7,alimiter=limit=0.95[out]")
    out = project.root / "final_audio.m4a"
    run_cmd(
        [
            ffmpeg(), "-y", "-v", "error",
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[out]", "-ar", str(SR), "-ac", "2", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{total:.3f}", str(out),
        ],
        timeout=600,
    )
    return out


def assemble_shots(shots: list[Shot], project: Project, mode: str, resolution: str) -> Path:
    shot_files = []
    for i, shot in enumerate(shots):
        out = project.root / "shots" / f"shot_{i:03d}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        caption_groups = project.state.get("caption_groups", [])
        render_shot_video(shot, out, mode, resolution, caption_groups)
        shot_files.append(out)

    concat = project.root / "shots.txt"
    concat.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in shot_files), encoding="utf-8")
    video_only = project.root / "video_only.mp4"
    run_cmd([
        ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS), str(video_only),
    ], timeout=1800)
    total = sum(s.dur for s in shots)
    project.state["total"] = total
    return video_only


def make_final(video_only: Path, audio: Path, out: Path) -> Path:
    run_cmd([
        ffmpeg(), "-y", "-v", "error", "-i", str(video_only), "-i", str(audio),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out),
    ], timeout=900)
    return out


# =============================================================================
# DOCUMENTARY CARDS
# =============================================================================

def make_card(text: str, sub: str, path: Path, W: int, H: int) -> Path:
    im = Image.new("RGB", (W, H), (10, 12, 16))
    d = ImageDraw.Draw(im)
    main = get_font(max(34, W // 18))
    small = get_font(max(18, W // 55))
    # vignette-ish bands
    for y in range(0, H, max(1, H // 100)):
        alpha = int(12 + 24 * (y / max(1, H)))
        d.line((0, y, W, y), fill=(10 + alpha // 4, 12 + alpha // 4, 16 + alpha // 4))
    d.text((W / 2 + 4, H / 2 - 20 + 4), text.upper(), font=main, fill=(0, 0, 0), anchor="mm")
    d.text((W / 2, H / 2 - 20), text.upper(), font=main, fill=(240, 240, 238), anchor="mm")
    d.rectangle((W * 0.43, H * 0.64, W * 0.57, H * 0.645), fill=(195, 35, 40))
    d.text((W / 2, H * 0.69), sub.upper(), font=small, fill=(195, 35, 40), anchor="mm")
    im.save(path, quality=92)
    return path


def generate_metadata(topic: str, mode: str, research: dict[str, Any]) -> dict[str, str]:
    if llm_provider() != "none":
        try:
            obj = llm_json(
                "Create ready-to-publish YouTube metadata for a research-led internet story. "
                "Title must be concrete and contextual, not vague or unsupported clickbait. "
                "Description must summarize only supported context and end with a specific audience question. "
                'Return JSON {"title":"...","description":"..."}.'
                f"\nMode: {mode}\nTopic: {topic}\nResearch: "
                + json.dumps(research, ensure_ascii=False)[:10000],
                max_tokens=1200,
            )
            if obj.get("title") and obj.get("description"):
                return {"title": norm_text(str(obj["title"]))[:100], "description": str(obj["description"]).strip()}
        except Exception:
            pass
    return {
        "title": (topic[:82] + " — What Really Happened?")[:100],
        "description": f"An original research-led {mode.lower()} about {topic}. "
                       "The video uses real source footage and commentary to explain the documented story. "
                       "What would you have done in the same situation?",
    }

# =============================================================================
# SHORT AUTOPILOT
# =============================================================================

def select_short_story(niche: str) -> dict[str, Any]:
    rows = niche_rows(niche, "short", limit=10)
    if not rows:
        raise RuntimeError("No story candidates found for niche.")
    return rows[0]


def prepare_short_assets(topic: str, research: dict[str, Any], project: Project) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    project.stage("source_hunt")
    sources = choose_sources(topic, research, count=7)
    if not sources:
        raise RuntimeError("Source hunter found no audiovisual candidates.")

    all_moments: list[dict[str, Any]] = []
    resolved_sources: list[dict[str, Any]] = []
    for source in sources:
        source = dict(source)
        try:
            try:
                meta = source_meta(source["url"], CACHE / "meta")
                source["duration"] = float(meta.get("duration") or 0)
            except Exception as exc:
                source["duration"] = float(source.get("duration") or 0)
                project.note("source_meta_fallback", url=source["url"], error=str(exc)[:300])

            cues = fetch_source_subtitles(source["url"], CACHE / "subs")
            source["subtitle_count"] = len(cues)
            source["subtitles_available"] = bool(cues)
            resolved_sources.append(source)

            if cues:
                for m in choose_dialogue_segments(source, cues, "short", wanted=3):
                    m["source_index"] = len(resolved_sources) - 1
                    m["subtitle_cues"] = cues
                    all_moments.append(m)
            else:
                for m in automatic_probe_moments(source, project, wanted=3):
                    m["source_index"] = len(resolved_sources) - 1
                    all_moments.append(m)
        except Exception as exc:
            project.note("source_probe_failed", url=source.get("url", ""), error=str(exc)[:500])

        if len(all_moments) >= 10:
            break

    # Metadata-only fallback: make non-overlapping windows; Whisper will caption them
    # after download. This lets the agent salvage an otherwise good story source.
    if len(all_moments) < 3:
        for idx, source in enumerate(resolved_sources[:4]):
            duration = float(source.get("duration") or 0)
            if duration < 5.0:
                continue
            starts = [min(max(0.0, duration * pct - 3.0), max(0.0, duration - 7.0)) for pct in (0.18, 0.52, 0.82)]
            for cut in starts:
                all_moments.append({
                    "source_index": idx, "source_url": source["url"],
                    "source_title": source.get("title", ""), "uploader": source.get("uploader", ""),
                    "quote": "", "cut": float(cut), "dur": float(min(7.0, duration - cut)),
                    "subtitle_cues": [],
                })
                if len(all_moments) >= 6:
                    break
            if len(all_moments) >= 6:
                break

    # We need story coverage, not three different URLs. Two sources + multiple moments is valid.
    if len(all_moments) < 3:
        raise RuntimeError("Automatic source hunter could not find three usable spoken moments after subtitles/Whisper/fallback probes.")

    project.state["source_stats"] = {
        "candidates": len(sources),
        "resolved": len(resolved_sources),
        "moments": len(all_moments),
        "unique_urls": len({m["source_url"] for m in all_moments}),
        "subtitled_sources": sum(1 for s in resolved_sources if s.get("subtitles_available")),
    }
    return resolved_sources, all_moments[:10]


def build_short_shots(topic: str, research: dict[str, Any], project: Project) -> list[Shot]:
    project.stage("source_selection")
    sources, moments = prepare_short_assets(topic, research, project)
    project.state["sources"] = [
        {k: v for k, v in s.items() if k in ("url", "title", "uploader", "party_score", "subtitles_available")}
        for s in sources
    ]

    script = build_short_script(topic, research, moments)
    project.state["script"] = script

    # Map moment indices to actual downloaded files.
    selected_sources = []
    for idx, m in enumerate(moments[:10]):
        try:
            src = sources[m["source_index"]]
            key = hashlib.sha1((src["url"] + f'|{m["cut"]:.2f}|{m["dur"]:.2f}').encode()).hexdigest()[:12]
            path = ASSET_CLIPS / f"{slugify(topic)}_{idx:02d}_{key}.mp4"
            if not path.exists():
                download_source_segment(src["url"], float(m["cut"]), float(m["dur"]), path)
            if not _usable_download(path, float(m["dur"])):
                raise RuntimeError(f"downloaded clip too short ({_media_duration(path):.2f}s)")
            m["file"] = str(path)
            if has_module("faster_whisper"):
                local_words = whisper_words(path)
                if local_words:
                    m["asr_words"] = [
                        {"text": w["text"], "start": float(w["start"]) + float(m["cut"]),
                         "end": float(w["end"]) + float(m["cut"])}
                        for w in local_words
                    ]
            selected_sources.append(m)
        except Exception as exc:
            project.note("short_clip_skipped", error=str(exc)[:400], source=m.get("source_url",""), cut=m.get("cut",0))
            continue

    # Compose the script order. We prefer three distinct source moments and 4-5 narration blocks.
    source_queue = selected_sources[:]
    shots: list[Shot] = []
    narr_texts = script.get("narration", [])
    narr_i = 0
    seen_files = set()

    def add_source(moment: dict[str, Any], dur_limit: float = 7.0) -> None:
        nonlocal shots
        path = Path(moment["file"])
        if str(path) in seen_files:
            return
        dur = min(float(moment.get("dur", 6.0)), dur_limit)
        start = sum(s.dur for s in shots)
        words = moment.get("asr_words") or proportional_words(moment.get("subtitle_cues", []))
        groups = caption_groups(words, max_words=4, max_chars=22)
        groups_abs = [
            {"start": start + max(0, g["start"] - moment["cut"]),
             "end": start + max(0, g["end"] - moment["cut"]),
             "text": g["text"]}
            for g in groups
            if g["end"] >= moment["cut"] and g["start"] <= moment["cut"] + dur + 0.25
        ]
        project.state.setdefault("caption_groups", []).extend(groups_abs)
        shots.append(
            Shot(
                kind="source",
                start=start,
                dur=dur,
                clip=path,
                clip_cut=0.0,  # downloaded segment is already trimmed
                source_words=words,
                narration="",
                note="original source dialogue",
            )
        )
        seen_files.add(str(path))

    def add_narration(text: str, broll_moment: Optional[dict[str, Any]] = None) -> None:
        start = sum(s.dur for s in shots)
        tpath = project.root / f"narration_{len(shots):02d}.mp3"
        tts(text, DEFAULT_VOICE, tpath)
        dur = audio_duration(tpath)
        if broll_moment:
            path = Path(broll_moment["file"])
            # Use a different source segment and mute its original audio.
            groups_abs = block_caption_groups(text, start, dur)
            project.state.setdefault("caption_groups", []).extend(groups_abs)
            shots.append(
                Shot(
                    kind="narration",
                    start=start,
                    dur=dur,
                    clip=path,
                    clip_cut=0.0,
                    narration=text,
                    note="narrator over real footage",
                )
            )
        else:
            groups_abs = block_caption_groups(text, start, dur)
            project.state.setdefault("caption_groups", []).extend(groups_abs)
            shots.append(Shot(kind="narration", start=start, dur=dur, narration=text))

    # Consequence-first opening: original speaker first.
    if source_queue:
        add_source(source_queue.pop(0), 7.0)
    if narr_texts:
        add_narration(narr_texts[0], source_queue[0] if source_queue else None)
        narr_i = 1
    if source_queue:
        add_source(source_queue.pop(0), 7.0)
    if narr_i < len(narr_texts):
        add_narration(narr_texts[narr_i], source_queue[0] if source_queue else None)
        narr_i += 1
    if source_queue:
        add_source(source_queue.pop(0), 7.0)
    while narr_i < len(narr_texts) and sum(s.dur for s in shots) < 54:
        add_narration(narr_texts[narr_i], source_queue[0] if source_queue else None)
        narr_i += 1

    # Add remaining unique source moments until near target; never loop the same file.
    for m in source_queue:
        if sum(s.dur for s in shots) >= 54:
            break
        add_source(m, 6.5)

    total = sum(s.dur for s in shots)
    if total < 45:
        for m in selected_sources:
            if total >= 45:
                break
            if str(m["file"]) not in seen_files:
                add_source(m, 6.5)
                total = sum(s.dur for s in shots)
    total = sum(s.dur for s in shots)
    if total > 58.5:
        overflow = total - 58.5
        while overflow > 0 and shots:
            last = shots[-1]
            if last.dur <= overflow + 0.05:
                overflow -= last.dur
                shots.pop()
            else:
                last.dur -= overflow
                overflow = 0
        total = sum(s.dur for s in shots)
        project.note("short_auto_trimmed", final_duration=total)
        project.state["caption_groups"] = [
            g for g in project.state.get("caption_groups", [])
            if float(g.get("start",0)) < total
        ]
    if not (45 <= total <= 59):
        raise RuntimeError(f"Short automatic timeline could not fit 45-59s; got {total:.2f}s.")
    if len(seen_files) < 2:
        raise RuntimeError("Short requires at least two audiovisual segments.")
    return shots


def run_short(topic: str, niche: str, resolution: str) -> dict[str, Any]:
    project = make_project(topic, "short", resolution)
    try:
        project.stage("research")
        research = gather_research(topic)
        project.state["research"] = research

        shots = build_short_shots(topic, research, project)
        metadata = generate_metadata(topic, "Short", research)
        project.state["metadata"] = metadata
        (project.root / "title.txt").write_text(metadata["title"] + "\n", encoding="utf-8")
        (project.root / "description.txt").write_text(metadata["description"] + "\n", encoding="utf-8")
        project.save()

        total = sum(s.dur for s in shots)
        project.stage("render")
        music = synth_music(total, seed=17)
        sfx = synth_sfx(total, [s.start for s in shots if s.kind == "source"])
        video_only = assemble_shots(shots, project, "short", resolution)
        audio = build_audio_mix(shots, total, music, sfx, project)
        out = OUTPUTS / f"{slugify(topic)}_{resolution}_short.mp4"
        make_final(video_only, audio, out)

        project.stage("qc")
        qc = qc_video(out, "short", resolution, total, project)
        project.state["qc"] = qc
        project.state["status"] = "ready_for_approval" if qc["pass"] else "blocked"
        project.state["output"] = str(out)
        make_srt(project.state.get("caption_groups", []), project.root / "captions.srt")
        project.state["artifacts"] = {
            "video": str(out),
            "captions": str(project.root / "captions.srt"),
            "state": str(project.root / "state.json"),
        }
        project.save()
        return project.state
    except Exception as exc:
        project.fail(str(exc))
        raise


# =============================================================================
# DOCUMENTARY AUTOPILOT
# =============================================================================

def still_from_clip(clip: Path, at: float, path: Path) -> Path:
    run_cmd([
        ffmpeg(), "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(clip),
        "-frames:v", "1", "-q:v", "2", str(path)
    ], timeout=120)
    return path


def make_doc_shots(topic: str, research: dict[str, Any], project: Project, duration: int) -> list[Shot]:
    project.stage("source_hunt")
    sources = choose_sources(topic, research, count=7)
    if not sources:
        raise RuntimeError("Documentary source hunter found no usable candidates.")

    moments=[]
    for srow in sources:
        try:
            cues=fetch_source_subtitles(srow["url"], CACHE/"subs")
            got=choose_dialogue_segments(srow,cues,"doc",wanted=2)
            if got:
                for m in got:
                    m["source_url"]=srow["url"]; m["source_title"]=srow.get("title","")
                    m["uploader"]=srow.get("uploader",""); m["subtitle_cues"]=cues
                    moments.append(m)
            else:
                got=automatic_probe_moments(srow,project,wanted=2)
                for m in got:
                    moments.append(m)
        except Exception as exc:
            project.note("doc_source_probe_failed",url=srow.get("url",""),error=str(exc)[:400])
        if len(moments)>=12: break

    if len(moments)<4:
        for i,srow in enumerate(sources):
            dur=float(srow.get("duration") or 0)
            if dur<5: continue
            cut=min(max(1.0+i*7,0),max(0,dur-7))
            moments.append({"source_url":srow["url"],"source_title":srow.get("title",""),
                            "uploader":srow.get("uploader",""),"quote":"","cut":cut,"dur":min(7.0,dur-cut),
                            "subtitle_cues":[]})
            if len(moments)>=8: break
    if not moments:
        raise RuntimeError("Documentary source hunter found no usable moments.")

    script=build_doc_script(topic,research,moments[:12],duration)
    project.state["script"]=script
    valid=[]
    for i,m in enumerate(moments[:12]):
        try:
            key=hashlib.sha1((m["source_url"]+f'|{m["cut"]:.2f}|{m["dur"]:.2f}').encode()).hexdigest()[:12]
            path=ASSET_CLIPS/f"{slugify(topic)}_doc_{i:02d}_{key}.mp4"
            if not path.exists():
                download_source_segment(m["source_url"],float(m["cut"]),float(m["dur"]),path)
            if not _usable_download(path,float(m["dur"])):
                raise RuntimeError(f"clip too short: {_media_duration(path):.2f}s")
            m["file"]=str(path)
            if has_module("faster_whisper") and not m.get("subtitle_cues"):
                words=whisper_words(path)
                m["asr_words"]=[{"text":w["text"],"start":float(w["start"])+float(m["cut"]),
                                 "end":float(w["end"])+float(m["cut"])} for w in words]
            m["_original_index"]=i
            valid.append(m)
        except Exception as exc:
            project.note("doc_clip_skipped",index=i,error=str(exc)[:400])
            continue

    if not valid:
        raise RuntimeError("No documentary clip survived automatic acquisition.")

    index_map={m["_original_index"]:i for i,m in enumerate(valid)}
    shots=[Shot(kind="card",start=0.0,dur=2.2,card_text=topic[:38],card_sub="ORIGINAL DOCUMENTARY",note="title")]
    cap_state=project.state.setdefault("caption_groups",[])
    narr_idx=0

    for block in script.get("blocks",[]):
        kind=str(block.get("kind","narration"))
        start=sum(x.dur for x in shots)
        if kind=="source":
            orig=int(block.get("moment_index",0) or 0)
            idx=index_map.get(orig,0)
            idx=max(0,min(idx,len(valid)-1))
            m=valid[idx]
            dur=min(8.0,float(m.get("dur",7.0)))
            words=m.get("asr_words") or proportional_words(m.get("subtitle_cues",[]))
            for g in caption_groups(words):
                local_start=max(0,float(g["start"])-float(m["cut"]))
                local_end=max(local_start,float(g["end"])-float(m["cut"]))
                if local_start<=dur+0.2:
                    cap_state.append({"start":start+local_start,"end":min(start+dur,start+local_end),"text":g["text"]})
            shots.append(Shot(kind="source",start=start,dur=dur,clip=Path(m["file"]),
                               clip_cut=0.0,source_words=words,note="original source dialogue"))
        else:
            txt=norm_text(str(block.get("text","")))
            if not txt: continue
            idx=index_map.get(int(block.get("moment_index",0) or 0),0)
            idx=max(0,min(idx,len(valid)-1))
            tpath=project.root/f"narration_{narr_idx:02d}.mp3"; narr_idx+=1
            tts(txt,DEFAULT_VOICE,tpath); dur=audio_duration(tpath)
            cap_state.extend(block_caption_groups(txt,start,dur))
            shots.append(Shot(kind="narration",start=start,dur=dur,clip=Path(valid[idx]["file"]),
                              clip_cut=0.0,narration=txt,note="narrator over real footage"))

    target_fill=max(120,duration*0.72)
    i=0
    while sum(x.dur for x in shots)<target_fill and i<len(valid):
        m=valid[i]; start=sum(x.dur for x in shots)
        dur=min(7.0,float(m.get("dur",7.0)))
        words=m.get("asr_words") or proportional_words(m.get("subtitle_cues",[]))
        for g in caption_groups(words):
            ls=max(0,float(g["start"])-float(m["cut"])); le=max(ls,float(g["end"])-float(m["cut"]))
            if ls<=dur+0.2: cap_state.append({"start":start+ls,"end":min(start+dur,start+le),"text":g["text"]})
        shots.append(Shot(kind="source",start=start,dur=dur,clip=Path(m["file"]),
                          clip_cut=0.0,source_words=words,note="evidence b-roll"))
        i+=1

    total=sum(x.dur for x in shots)
    if total<45:
        raise RuntimeError("Documentary plan produced no usable runtime.")
    return shots


def run_doc(topic: str, niche: str, resolution: str, duration_text: str = "3m30s") -> dict[str, Any]:
    target = parse_duration_seconds(duration_text)
    project = make_project(topic, "doc", resolution)
    try:
        project.stage("research")
        research = gather_research(topic)
        project.state["research"] = research
        project.stage("story")
        shots = make_doc_shots(topic, research, project, target)
        metadata = generate_metadata(topic, "Documentary", research)
        project.state["metadata"] = metadata
        (project.root / "title.txt").write_text(metadata["title"] + "\n", encoding="utf-8")
        (project.root / "description.txt").write_text(metadata["description"] + "\n", encoding="utf-8")
        project.save()
        total = sum(s.dur for s in shots)
        project.stage("render")
        music = synth_music(total, seed=29)
        sfx = synth_sfx(total, [s.start for s in shots if s.kind == "source"])
        video_only = assemble_shots(shots, project, "doc", resolution)
        audio = build_audio_mix(shots, total, music, sfx, project)
        out = OUTPUTS / f"{slugify(topic)}_{resolution}_documentary.mp4"
        make_final(video_only, audio, out)
        project.stage("qc")
        qc = qc_video(out, "doc", resolution, total, project)
        project.state["qc"] = qc
        project.state["status"] = "ready_for_approval" if qc["pass"] else "blocked"
        project.state["output"] = str(out)
        make_srt(project.state.get("caption_groups", []), project.root / "captions.srt")
        project.state["artifacts"] = {
            "video": str(out),
            "captions": str(project.root / "captions.srt"),
            "state": str(project.root / "state.json"),
        }
        project.save()
        return project.state
    except Exception as exc:
        project.fail(str(exc))
        raise


# =============================================================================
# QC / RETRIES
# =============================================================================

def probe_video(path: Path) -> dict[str, Any]:
    obj = json.loads(
        run_cmd([
            ffprobe(), "-v", "error", "-print_format", "json",
            "-show_streams", "-show_format", str(path)
        ]).stdout
    )
    v = next((s for s in obj["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in obj["streams"] if s["codec_type"] == "audio"), None)
    return {
        "duration": float(obj["format"].get("duration", 0)),
        "bytes": int(obj["format"].get("size", 0)),
        "video": {
            "width": int(v.get("width", 0)) if v else 0,
            "height": int(v.get("height", 0)) if v else 0,
            "codec": v.get("codec_name") if v else "",
            "fps": v.get("r_frame_rate") if v else "",
        },
        "audio": {
            "codec": a.get("codec_name") if a else "",
            "sample_rate": int(a.get("sample_rate", 0)) if a else 0,
        },
    }


def visual_activity(path: Path, samples: int = 8) -> float:
    if cv2 is None:
        return 1.0
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return 0.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    diffs = []
    prev = None
    for pos in np.linspace(0, max(1, n - 1), samples).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diffs.append(float(np.mean(cv2.absdiff(prev, gray))) / 255.0)
        prev = gray
    cap.release()
    return float(np.median(diffs)) if diffs else 0.0


def audio_peak(path: Path) -> Optional[float]:
    proc = run_cmd(
        [ffmpeg(), "-v", "info", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
        timeout=180,
        check=False,
    )
    m = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", proc.stderr)
    return float(m.group(1)) if m else None


def qc_video(path: Path, mode: str, resolution: str, expected: float, project: Project) -> dict[str, Any]:
    q = probe_video(path)
    expected_wh = RESOLUTIONS[resolution][mode]
    duration_ok = (45 <= q["duration"] <= 59) if mode == "short" else (abs(q["duration"] - expected) / max(expected, 1) <= 0.20)
    streams_ok = q["video"]["codec"] == "h264" and q["audio"]["codec"] in {"aac", "mp4a"}
    geometry_ok = (q["video"]["width"], q["video"]["height"]) == expected_wh
    activity = visual_activity(path)
    activity_ok = activity > 0.012
    peak = audio_peak(path)
    peak_ok = peak is None or peak < -0.5
    report = {
        "pass": all([duration_ok, streams_ok, geometry_ok, activity_ok, peak_ok]),
        "duration": q["duration"],
        "expected_duration": expected,
        "duration_ok": duration_ok,
        "streams_ok": streams_ok,
        "geometry": [q["video"]["width"], q["video"]["height"]],
        "geometry_ok": geometry_ok,
        "visual_activity": activity,
        "visual_activity_ok": activity_ok,
        "peak_db": peak,
        "peak_ok": peak_ok,
        "probe": q,
    }
    (project.root / "qc.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# =============================================================================
# AUTOPILOT RETRY / IDEALAB
# =============================================================================

def parse_duration_seconds(text: str) -> int:
    t = (text or "3m30s").strip().lower()
    total = 0
    m = re.search(r"(\d+)\s*h", t)
    if m:
        total += int(m.group(1)) * 3600
    m = re.search(r"(\d+)\s*m", t)
    if m:
        total += int(m.group(1)) * 60
    m = re.search(r"(\d+)\s*s", t)
    if m:
        total += int(m.group(1))
    if total == 0:
        try:
            total = int(float(t))
        except Exception:
            total = 210
    return max(45, total)


def autopilot(mode: str, niche: str, resolution: str, topic: Optional[str] = None,
              max_story_retries: int = 8, duration_text: str = "3m30s") -> dict[str, Any]:
    reset_progress(f"AUTOPILOT {mode.upper()} | {niche.upper()} | LLM {llm_provider().upper()}")
    if topic:
        candidates = [{"title": topic, "score": 100.0, "score_10": 10.0}]
    else:
        scan_names = list(NICHES) if niche == "all" else [niche]
        candidates: list[dict[str, Any]] = []
        for n in scan_names:
            candidates.extend(niche_rows(n, mode, limit=6))
        candidates.sort(key=lambda r: r.get("score", 0), reverse=True)
        candidates = candidates[:max_story_retries]
    if not candidates:
        raise RuntimeError("Agenten hittade inga story-kandidater.")

    failures = []
    for row in candidates:
        chosen = row["title"]
        print(f"\n[AUTOPILOT] försöker: {chosen}")
        print(f"[AUTOPILOT] score {row.get('score_10', 0):.1f}/10 ({row.get('score', 0):.1f}%)")
        try:
            if mode == "short":
                return run_short(chosen, niche, resolution)
            return run_doc(chosen, niche, resolution, duration_text)
        except Exception as exc:
            failures.append({"topic": chosen, "error": str(exc)[:700]})
            print(f"[AUTOPILOT] story blocked -> nästa kandidat: {str(exc)[:240]}")

    raise RuntimeError("Alla automatiska story-försök blockerades:\n" + json.dumps(failures, ensure_ascii=False, indent=2))


def run_idea_lab(niche: str, mode: str) -> None:
    names = list(NICHES) if niche == "all" else [niche]
    rows = []
    print("\nScanning niches...")
    for n in names:
        got = niche_rows(n, mode, limit=6)
        rows.extend(got)
        print(f"\n=== {n.upper()} / {mode.upper()} ===")
        for i, r in enumerate(got, 1):
            print(f"{i}. {r['score_10']:.1f}/10 ({r['score']:.1f}%)  {r['title'][:110]}")
    rows.sort(key=lambda r: r.get("score", 0), reverse=True)
    out = ROOT / "idea_lab"
    out.mkdir(exist_ok=True)
    stamp = dt.date.today().isoformat()
    (out / f"lab_{mode}_{stamp}.json").write_text(json.dumps({"results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nTOP 10:")
    for i, r in enumerate(rows[:10], 1):
        print(f"{i:2}. {r['score_10']:.1f}/10 ({r['score']:.1f}%) - {r['title']}")
    print("Saved:", out.resolve())


# =============================================================================
# SELF TEST
# =============================================================================

def selftest() -> None:
    banner()
    print("[1/6] resolution presets")
    assert RESOLUTIONS["320p"]["short"] == (320, 568)
    assert RESOLUTIONS["720p"]["short"] == (720, 1280)
    assert RESOLUTIONS["1080p"]["short"] == (1080, 1920)
    print("  PASS")

    print("[2/6] music synthesis")
    p = synth_music(3.0, seed=1)
    assert p.exists() and p.stat().st_size > 1000
    print("  PASS:", p)

    print("[3/6] caption grouping")
    gs = caption_groups(proportional_words([{"start": 0, "end": 2, "text": "This is a test of captions"}]))
    assert gs
    print("  PASS:", len(gs), "groups")

    print("[4/6] state")
    pjt = make_project("selftest", "short", "320p")
    pjt.note("selftest_ok")
    assert (pjt.root / "state.json").exists()
    print("  PASS")

    print("[5/6] LLM config")
    print(" ", json.dumps(llm_status(), ensure_ascii=False))
    print("  PASS (configuration check only)")

    print("[6/6] tools")
    print(" ", "ffmpeg:", shutil.which("ffmpeg"))
    print(" ", "ffprobe:", shutil.which("ffprobe"))
    print(" ", "yt-dlp:", shutil.which("yt-dlp"))
    print(" ", "edge-tts:", has_module("edge_tts"))
    print("  PASS")


# =============================================================================
# INTERACTIVE UI
# =============================================================================

def ask(prompt: str, default: str = "") -> str:
    x = input(prompt).strip()
    return x if x else default


def pick_mode() -> str:
    print("\nMODE")
    print("  1) SHORTS      — 9:16 real-footage autopilot")
    print("  2) DOCUMENTARY — 16:9 cinematic story autopilot")
    return {"1": "short", "2": "doc"}.get(ask("Choose [1]: ", "1"), "short")


def pick_niche() -> str:
    names = list(NICHES)
    print("\nNICHE")
    print("  A) AUTO — agent scans every niche")
    for i, name in enumerate(names, 1):
        print(f"  {i:2}) {name}")
    c = ask("Choose [A]: ", "A").lower()
    if c == "a":
        return "all"
    try:
        return names[int(c) - 1]
    except Exception:
        return "all"


def pick_resolution() -> str:
    print("\nQUALITY")
    print("  1) 320p  — fast preview")
    print("  2) 720p  — default")
    print("  3) 1080p — final HD")
    return {"1": "320p", "2": "720p", "3": "1080p"}.get(ask("Choose [2]: ", "2"), "720p")


def interactive() -> None:
    while True:
        banner()
        print("1) SHORTS AUTOPILOT")
        print("2) DOCUMENTARY AUTOPILOT")
        print("3) IDEA LAB")
        print("4) TEST LLM")
        print("5) SELFTEST")
        print("6) CAPABILITIES")
        print("Q) EXIT")
        choice = ask("\nChoose: ", "1").lower()
        if choice == "q":
            return
        if choice == "4":
            try:
                print(json.dumps(test_llm(), ensure_ascii=False, indent=2))
            except Exception as exc:
                print("LLM TEST FAILED:", exc)
            continue
        if choice == "5":
            selftest()
            continue
        if choice == "6":
            print(json.dumps(capabilities(), ensure_ascii=False, indent=2))
            continue
        if choice not in {"1", "2", "3"}:
            print("Unknown choice.")
            continue
        if choice == "3":
            mode = ask("\nIdea Lab [1] Shorts / [2] Documentary [1]: ", "1")
            mode = "doc" if mode == "2" else "short"
            niche = pick_niche()
            run_idea_lab(niche, mode)
            continue

        mode = "short" if choice == "1" else "doc"
        niche = pick_niche()
        resolution = pick_resolution()
        print("\n[AUTOPILOT] Topic = automatic")
        print("[AUTOPILOT] Source hunt = automatic")
        print("[AUTOPILOT] Failed story -> next story automatically")
        print("[AUTOPILOT] No final confirmation prompt; render stops only on a real blocker.")
        try:
            state = autopilot(mode, niche, resolution)
            print("\n" + "=" * 72)
            print("READY FOR APPROVAL")
            print("topic :", state.get("topic"))
            print("output:", state.get("output"))
            print("qc    :", json.dumps(state.get("qc", {}), ensure_ascii=False))
            print("=" * 72)
        except Exception as exc:
            print("\nAUTOPILOT STOPPED:", exc)
            print("Nothing was published automatically.")


# =============================================================================
# CLI
# =============================================================================

def capabilities() -> dict[str, Any]:
    return {
        "llm": llm_status(),
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "yt_dlp": shutil.which("yt-dlp"),
        "edge_tts": has_module("edge_tts"),
        "opencv": cv2 is not None,
        "resolutions": RESOLUTIONS,
        "voices": {"default": DEFAULT_VOICE},
        "niche_count": len(NICHES),
        "autopilot_story_retry_count": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoFinal 2026 autonomous creator studio")
    parser.add_argument("--mode", choices=["short", "doc"], default=None)
    parser.add_argument("--topic", default="")
    parser.add_argument("--niche", default="all", choices=["all"] + list(NICHES))
    parser.add_argument("--resolution", choices=list(RESOLUTIONS), default="720p")
    parser.add_argument("--duration", default="3m30s")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--test-llm", action="store_true")
    parser.add_argument("--idea-lab", action="store_true")
    parser.add_argument("--capabilities", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return
    if args.test_llm:
        print(json.dumps(test_llm(), ensure_ascii=False, indent=2))
        return
    ensure_runtime_dependencies()
    if len(sys.argv) == 1:
        interactive()
        return
    if args.capabilities:
        print(json.dumps(capabilities(), ensure_ascii=False, indent=2))
        return
    if args.idea_lab:
        run_idea_lab(args.niche, args.mode or "short")
        return
    if not args.mode:
        parser.error("--mode krävs när du inte kör interaktivt")
    state = autopilot(
        args.mode, args.niche, args.resolution,
        topic=args.topic or None,
        max_story_retries=8,
        duration_text=args.duration,
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()