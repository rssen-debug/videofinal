#!/usr/bin/env python3
"""engine/media.py — snabb inspect/heal av media (durations, RMS-toppar,
klipptrimning, format-normalisering) utan ffprobe (ffmpeg -i + regex).
"""
import os, re, subprocess, sys

def ffmpeg():
    from research import sources
    try:
        return sources.ensure_ffmpeg()
    except Exception:
        return "ffmpeg"

def run(args, label="media"):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{label}: " + r.stderr[-1200:])
    return r

def probe(path):
    r = subprocess.run([ffmpeg(), "-i", path], capture_output=True, text=True)
    info = r.stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", info)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    has_v = bool(re.search(r"Stream #\S+:.*Video", info))
    has_a = bool(re.search(r"Stream #\S+:.*Audio", info))
    res = None
    m2 = re.search(r"(\d{3,4})x(\d{3,4})", info)
    if m2:
        res = (int(m2.group(1)), int(m2.group(2)))
    return {"duration": dur, "video": has_v, "audio": has_a, "res": res,
            "raw": info}

def to_wav(src, dst):
    """Convertera ev. ljud-/videofil till 44.1k mono wav (för wave-modulen)."""
    run([ffmpeg(), "-y", "-v", "error", "-i", src, "-vn", "-ac", "1",
         "-ar", "44100", dst], "to_wav")
    return dst

def rms_series(path, win=0.5, sr=8000):
    r = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-map", "0:a?",
                        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True)
    if not r.stdout:
        return []
    import numpy as np
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768
    n = int(sr * win)
    return [float(np.sqrt(np.mean(x[i:i + n] ** 2)) + 1e-9)
            for i in range(0, max(len(x) - n, 1), n)]

def rms_peak_time(path, win=0.5):
    """Returnerar (tiden, rms) för det mest högljudda fönstret — ögonblicket."""
    ser = rms_series(path, win=win)
    if not ser:
        return 0.0, 0.0
    i = int(max(range(len(ser)), key=lambda j: ser[j]))
    return i * win, ser[i]

def extract_clip(src, cut, dur, dst, h=480, fps=30, crop=""):
    """Klipp + normalisera MED LJUD behållet (MANDATE: klipp ska ha ljud):
    scale -> set-sar -> yuv420p, fast fps, aac-ljud."""
    vf = f"{crop}scale=-2:{h},fps={fps},setsar=1"
    run([ffmpeg(), "-y", "-v", "error", "-ss", str(cut), "-t", str(dur),
         "-i", src, "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ac", "2",
         "-movflags", "+faststart", dst],
        "extract_clip")
    return dst

def grid(src, dst, cols=3, rows=3, top=9):
    """Kontaktblad (grid) av stills var N sek — för att VÄLJA ögonblick."""
    probe_d = probe(src)["duration"]
    step = max(1.0, probe_d / (cols * rows))
    fs = []
    for i in range(cols * rows):
        t = min(i * step + step / 2, probe_d - 0.1)
        f = dst.replace(".jpg", f"_{i}.jpg")
        run([ffmpeg(), "-y", "-v", "error", "-ss", str(t), "-i", src,
             "-frames:v", "1", "-vf", "scale=320:180", f], "grid frame")
        fs.append(f)
    try:
        from PIL import Image
        thumbs = [Image.open(f) for f in fs[:top]]
        w, h = thumbs[0].size
        canvas = Image.new("RGB", (cols * w, rows * h), "#000")
        for i, im in enumerate(thumbs):
            canvas.paste(im, ((i % cols) * w, (i // cols) * h))
        canvas.save(dst, quality=90)
    except Exception:
        pass
    return dst
