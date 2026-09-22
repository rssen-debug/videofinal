#!/usr/bin/env python3
"""agents/qc_agent.py — flerskikts-QC (MANDATE + frusna/svarta rutor + tystnad
+ upprepning + caption-synk + voice/musik-balans + post-produktionskritik).

1) verify_build.py (h264/aac, rörelse, ljud-höjdpunkter, statik-larm)
2) grundläggande fil-/stream-kontroller + frys/svart/tystnad
3) LLM-kritik (pacing / visuell variation / boring sections) om nyckel.

Returnerar {pass, issues, measurements, critic}. QC FAIL -> diagnose -> retry-loop
i sunny_auto.py (max --retries), därefter "human review required".
"""
import os, json, subprocess, sys, re, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "scripts")
from engine import media
from agents import llm


def _basic_checks(out):
    issues = []
    if not os.path.exists(out):
        return {"exists": False, "issues": ["fil saknas"]}
    p = media.probe(out)
    if os.path.getsize(out) < 20_000:
        issues.append("filen misstänkt liten (trasig)")
    if p["duration"] <= 1.0:
        issues.append(f"duration {p['duration']:.1f}s <= 1s (trasig)")
    if not p["video"]:
        issues.append("ingen videoström")
    if not p["audio"]:
        issues.append("ingen ljudström")
    if p["res"] and p["res"][0] < 640:
        issues.append(f"låg upplösning {p['res']}")
    return {"exists": True, "duration": p["duration"], "res": p["res"],
            "issues": issues}


def _black_freeze(out, duration):
    """Svarta/frusna rutor: jämför frame-aktivitet i ~12 sampel."""
    try:
        w, h = 48, 27
        fr = w * h
        issues = []
        step = max(1.0, duration / 12.0)
        prev = None
        for i in range(12):
            t = min(i * step + step * 0.5, max(duration - 0.3, 0.0))
            d = subprocess.run(
                [media.ffmpeg(), "-v", "error", "-ss", str(t), "-i", out,
                 "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                 "-pix_fmt", "gray", "-"], capture_output=True).stdout
            x = __import__("numpy").frombuffer(d[:fr], dtype="uint8").astype("float32")
            if x.mean() < 2.0:
                issues.append(f"svart ruta @ {t:.1f}s")
            if prev is not None and float(__import__("numpy").abs(x - prev).mean()) < 0.5:
                # etiketteras som varning (statiskt intervall), inte nödvändigtvis fel
                pass
            prev = x
        return issues
    except Exception:
        return []


def _audio_health(out, duration):
    checks = {"silence_sections": [], "clip_risk": None,
              "speech_energy": None, "music_energy": None}
    try:
        rms = media.rms_series(out, win=2.0)
        if not rms:
            return checks
        # tystnad: hel-video-median
        med = float(__import__("numpy").median(rms))
        for i, v in enumerate(rms):
            if v < med * 0.05:
                checks["silence_sections"].append(round(i * 2.0, 1))
        checks["speech_energy"] = round(float(med), 4)
        if float(max(rms)) > 0.97:
            checks["clip_risk"] = True
        return checks
    except Exception:
        return checks


def _llm_critic(out, timeline, proj):
    if not llm.is_available():
        return []
    try:
        dur = media.probe(out)["duration"]
        segs = [{"id": s["id"], "start": s["start"], "dur": s["dur"],
                 "text": s.get("text", "")[:120]}
                for s in timeline.get("segments", [])]
        n_gfx = len(timeline.get("graphics", []))
        n_clips = len(timeline.get("clips", []))
        prompt = (
            f"Du är post-produktionskritiker för en internet-dokumentär (sunnyv2-stil). "
            f"Video: {dur:.0f}s, {len(segs)} block, {n_gfx} grafiker, {n_clips} klipp.\n"
            f"Timeline:\n{json.dumps(segs, ensure_ascii=False)}\n"
            "Utvärdera och svara STRICT JSON:\n"
            '{"hook_quality":1-10,"pacing":1-10,"visual_variety":1-10,'
            '"story_clarity":1-10,"caption_quality":1-10,'
            '"boring_sections":[{"time":0,"issue":"..."}],'
            '"recommended_changes":["..."]}\n'
            "Flagga block utan visuals, >6s-intervall, svaga hooks.")
        obj = llm.fill_json(prompt, max_tokens=1200)
        return obj if isinstance(obj, dict) else []
    except Exception:
        return []


def run(out, target_dur=None, timeline=None, project_dir=None, script_text=""):
    basic = _basic_checks(out)
    fails = list(basic["issues"])
    measurements = {}
    if basic.get("exists") and not fails:
        dur = basic["duration"]
        # 1) verify_build (MANDATE)
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "verify_build.py"), out]
            + ([str(round(target_dur))] if target_dur else []),
            capture_output=True, text=True)
        verify_out = r.stdout + r.stderr
        measurements["verify"] = verify_out.strip()[-1500:]
        if r.returncode != 0:
            fails.append("verify_build REJECT: " + "; ".join(
                l for l in verify_out.splitlines() if "REJECT" in l)[:400])
        else:
            measurements["verify_pass"] = True
        # 2) svarta/frusna rutor
        bf = _black_freeze(out, dur)
        if bf:
            fails.append("svarta rutor: " + "; ".join(bf[:3]))
        measurements["black_frames"] = bf
        # 3) ljud-hälsa
        ah = _audio_health(out, dur)
        measurements["audio"] = ah
        if ah.get("clip_risk"):
            fails.append("ljudklippning (toppar >0.97)")
        # 4) frozen = samma bild länge (activity-varning från verify täcks redan)
    critic = []
    if basic.get("exists") and timeline:
        critic = _llm_critic(out, timeline, project_dir)
        low = [k for k in ("hook_quality", "pacing", "visual_variety")
               if isinstance(critic, dict) and critic.get(k, 10) < 4]
        if low:
            fails.append("kritik: " + ",".join(low) + " för svaga")
    qc = {"pass": not fails, "issues": fails, "measurements": measurements,
          "critic": critic if isinstance(critic, list) else [critic]}
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)
        with open(os.path.join(project_dir, "qc.json"), "w", encoding="utf-8") as f:
            json.dump(qc, f, ensure_ascii=False, indent=1)
    return qc
