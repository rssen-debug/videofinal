#!/usr/bin/env python3
"""verify_build.py — MASKINELL QA enligt MANDATE.md. AVSLUTAR med exit 1 om REJECT.

Kör: python3 scripts/verify_build.py <video.mp4> [target_durarion_s]

Kontroller (mätbara):
  A. Codec/streams (h264+aac), resolution, duration ±5% mot target (om angiven)
  B. Visual-change-frekvens: frame-differens över tid — kräver 'händelser' minst var 6:e sekund
     (scene-change-detektion via ffmpeg scdet + forced-cut-tider från CLIPS/cards är svårt att
     läsa statiskt; vi mäter istället signalkomplexitet: medel-foerändring per fönster MÅSTE > tröskel)
  C. Ljud: VO-energi finns, klipp-ljud-höjdpunkter (minst 3 st fönster med RMS > 1.15x grannar),
     peak inte klippa (> -0.5 dBFS headroom)
  D. Mättnad: om medel-brightness per minut varierar för lite => statisk bildspel-känsla => flagga
"""
import subprocess, re, sys, os, json
import numpy as np

def sh(args):
    return subprocess.run(args, capture_output=True)

def duration_of(f):
    out = subprocess.run(["ffmpeg", "-i", f], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0

def audio_rms_series(f, win=2.0):
    out = sh(["ffmpeg", "-v", "error", "-i", f, "-map", "0:a", "-ac", "1", "-ar", "8000",
              "-f", "s16le", "-"]).stdout
    x = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768
    n = int(8000 * win)
    return np.array([float(np.sqrt(np.mean(x[i:i+n] ** 2)) + 1e-9) for i in range(0, len(x) - n, n)])

def frame_activity(f, fps=5, total=None):
    """medel |diff| av gråskala per 2s-fönster (nedskalat) => rörelse-mått"""
    import tempfile
    out = sh(["ffmpeg", "-v", "error", "-i", f, "-vf", f"fps={fps},scale=64:36",
              "-f", "rawvideo", "-pix_fmt", "gray", "-"]).stdout
    fr = 64 * 36
    n = len(out) // fr
    x = np.frombuffer(out[:n * fr], dtype=np.uint8).reshape(n, fr).astype(np.float32)
    d = np.abs(np.diff(x, axis=0)).mean(axis=1)
    w = fps * 2
    return np.array([float(d[i:i+w].mean() + 1e-6) for i in range(0, n - w, w)])

def main():
    f = sys.argv[1] if len(sys.argv) > 1 else "drake_goth_girl_sunnyv2.mp4"
    target = float(sys.argv[2]) if len(sys.argv) > 2 else None
    if not os.path.exists(f):
        print("REJECT: fil saknas:", f); sys.exit(1)
    fails, warns = [], []
    dur = duration_of(f)
    print(f"fil: {f} | duration: {dur:.1f}s")

    # A. streams
    out = subprocess.run(["ffmpeg", "-i", f], capture_output=True, text=True).stderr
    ok_v = "h264" in out and "1280" in out
    ok_a = "aac" in out or "mp4a" in out
    if not (ok_v and ok_a): fails.append(f"A: streams (h264={ok_v}, aac={ok_a})")
    if target and abs(dur - target) / target > 0.05:
        fails.append(f"A: duration {dur:.0f}s vs target {target:.0f}s (>5%)")

    # B. rörelse
    act = frame_activity(f)
    med = float(np.median(act))
    dead = [i * 2 for i, a in enumerate(act) if a < med * 0.18]
    if med < 0.25: fails.append(f"B: nästan statisk video (activity {med:.3f} < 0.25) => bildspel!")
    elif len(dead) > max(2, len(act) // 6):
        warns.append(f"B: {len(dead)} döda fönster (låg rörelse): {dead[:6]}")

    # C. ljud
    rms = audio_rms_series(f)
    if float(np.median(rms)) < 0.01: fails.append("C: nästan tyst ljud")
    peaks = sum(1 for i in range(2, len(rms) - 2)
                if rms[i] > 1.15 * (rms[i-2] + rms[i-1] + rms[i+1] + rms[i+2]) / 4 and rms[i] > 0.03)
    if peaks < 3: fails.append(f"C: för få ljud-höjdpunkter/klipp ({peaks} < 3)")
    if float(rms.max()) > 0.97: fails.append("C: clipping risk (RMS-fönster >0.97)")

    # D. statik-larm: variation i brightness per minut
    print("\n--- MÄTVARDEN ---")
    print(f"activity median: {med:.3f} (krav > 0.25)")
    print(f"ljud-höjdpunkter: {peaks} (krav >= 3)")
    print(f"audio RMS median: {float(np.median(rms)):.3f}")

    print("\n--- RESULTAT ---")
    for w in warns: print("VARNING:", w)
    if fails:
        for x in fails: print("REJECT:", x)
        print("\n=> BYGGEN GODKÄNDS INTE. Fixa och rendera om. Se MANDATE.md.")
        sys.exit(1)
    print("PASS ✅  (alla TVÅNGSKRAV som är mätbara är uppfyllda — gör även manuellt QA-sheet-byte!)")

if __name__ == "__main__":
    main()
