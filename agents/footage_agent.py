#!/usr/bin/env python3
"""agents/footage_agent.py — fotage-motorn:
1) för varje clip_plan-rad: sök (YouTube via yt-dlp; fallback: befintliga klipp)
2) ladda ner, hitta "ögonblicket" (RMS-topp), trimma, normalisera
3) licens-tagga → clips.json
Syfte: footage KOPPLAS till narration, inte random B-roll.
"""
import os, json, subprocess, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPDIR = os.path.join(ROOT, "assets", "clips")
os.makedirs(CLIPDIR, exist_ok=True)
from research import sources as S
from engine import media

def _existing_clips():
    return sorted(glob.glob(os.path.join(CLIPDIR, "*.mp4")))

def _download_yt(vid, dest, h=480):
    fm = S.ensure_ffmpeg()
    exe = sys.executable
    # ladda ljud+video separat -> egen mux (PIPELINE §7)
    cmd = [exe, "-m", "yt_dlp", "--no-warnings",
           "-f", f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/b[height<={h}]",
           "-o", f"{dest}.%(ext)s", f"https://www.youtube.com/watch?v={vid}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])
    v = f"{dest}.mp4"; a = f"{dest}.m4a"
    if os.path.exists(v) and os.path.exists(a):
        subprocess.run([fm, "-y", "-v", "error", "-i", v, "-i", a, "-c", "copy",
                        "-movflags", "+faststart", dest], check=True)
        for p in (v, a):
            os.path.exists(p) and os.remove(p)
    elif os.path.exists(v):
        os.rename(v, dest)
    else:
        webm = f"{dest}.webm"
        if os.path.exists(webm):
            os.rename(webm, dest)
    if not os.path.exists(dest):
        raise RuntimeError("nedladdning misslyckades för " + vid)

def run(plan, slug, project_dir, max_clips=6):
    """Returnerar {number: clip_filename}. Skriver clips.json."""
    clip_files, log = {}, []
    existing = _existing_clips()

    def fallback_local(query, number):
        """Återanvänd ENDAST lokala klipp som är ämnesrelevanta (slug i namnet)."""
        rel = [f for f in existing if slug.lower() in os.path.basename(f).lower()]
        if rel:
            f = rel[number % len(rel)]
            return os.path.basename(f), {"license": "demo", "source": "repo"}
        return None, None

    for c in plan.get("clip_plan", [])[:max_clips]:
        number = str(c.get("number", len(clip_files) + 1))
        query = c.get("query", "") or plan.get("topic", slug)
        dest = os.path.join(CLIPDIR, f"{slug}_clip{number}.mp4")
        src_meta = {"license": "youtube", "source": "youtube"}
        got = False
        # 1) försök YouTube
        cands = S.youtube_search(query, limit=6, max_dur=240)
        for cand in cands:
            try:
                _download_yt(cand["id"], dest)
                got = True
                src_meta = {"license": "youtube", "source": cand["channel"] or "youtube",
                            "url": cand["url"]}
                break
            except Exception:
                continue
        # 2) fallback: återanvänd lokala klipp (demo)
        if not got:
            fname, meta = fallback_local(query, int(number))
            if fname:
                dest = os.path.join(CLIPDIR, fname)
                src_meta = meta or src_meta
                got = True
        if not got:
            log.append({"number": number, "query": query, "status": "skipped",
                        "reason": "ingen kandidat (offline/blockerad)"})
            continue

        # välj ögonblick: RMS-topp om vo­lym finns, annars mitten
        cut = float(c.get("cut", 0))
        if cut == 0:
            try:
                peak_t, _ = media.rms_peak_time(dest)
                total = media.probe(dest)["duration"]
                cut = max(0.0, peak_t - 1.0)
                if cut + float(c.get("dur", 6)) > total:
                    cut = max(0.0, total - float(c.get("dur", 6)))
                c["cut"] = round(cut, 2)
            except Exception:
                pass
        # trim + normalisera (crop endast om det är ett ffmpeg-vf-uttryck)
        raw_crop = c.get("crop", "") or ""
        crop = raw_crop if str(raw_crop).startswith("crop=") else ""
        try:
            tmp = dest + ".trim.mp4"
            media.extract_clip(dest, cut, float(c.get("dur", 6)), tmp, h=480,
                               crop=crop)
            os.replace(tmp, dest)
        except Exception as e:
            log.append({"number": number, "status": "trim-error",
                        "reason": str(e)[:200]})
        clip_files[number] = os.path.basename(dest)
        log.append({"number": number, "query": query, "file": os.path.basename(dest),
                    "cut": round(cut, 2), "status": "ok",
                    "license": src_meta["license"], "source": src_meta.get("source")})

    with open(os.path.join(project_dir, "clips.json"), "w", encoding="utf-8") as f:
        json.dump({"clips": log, "files": clip_files}, f, ensure_ascii=False, indent=1)
    return clip_files
