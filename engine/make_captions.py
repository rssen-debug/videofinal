#!/usr/bin/env python3
"""CAPTIONS v2 — kinetic typography (sunnyv2/Shorts-pop, UPPGRADERAD):
  * Archivo Black (display-font), tyngre outline
  * KEYWORD-HIGHLIGHT: ord i keywords.txt (case-insens) blir RÖDA + storleks-pop
  * rotation-jitter per event (organiskt, inte mekaniskt)
  * grupper om <=3 ord / <=16 tecken, pop-in 62->100% paa 70 ms

Funktioner kan importeras: build_events(), ts(), HEADER()
Kör som script -> timings.json + captions.ass (hela videon)
"""
import os, json, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "script", "script.txt")
AUDIO = os.path.join(ROOT, "audio")
GAP = 0.7
TAIL = 0.5
LEAD = 0.10

def wav_dur(p):
    with wave.open(p, "rb") as w:
        return w.getnframes() / w.getframerate()

def load_keywords():
    p = os.path.join(ROOT, "keywords.txt")
    if os.path.exists(p):
        return {l.strip().lower() for l in open(p, encoding="utf-8") if l.strip()}
    return set()

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Archivo Black,54,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,92,1
Style: PopBig,Archivo Black,68,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,92,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def ts(x):
    h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return f"{h}:{m:02d}:{s:05.2f}"

RED = r"{\c&H2E22E8&}"      # BGR för accent-röd (232,34,46)
WHITE = r"{\c&HFFFFFF&}"

def build_events(segments, keywords, lead=LEAD, jitter=True):
    """segments: [{id,text,start,dur}] -> [(start, end, ass_text)]"""
    ev = []
    for s in segments:
        words = s["text"].split()
        weights = [len(w) + 2 for w in words]
        t0 = s["start"] + lead
        span = max(s["dur"] - lead - 0.15, 0.4)
        wt, acc = [], t0
        for w, ww in zip(words, weights):
            d = span * ww / sum(weights)
            wt.append((w, acc, acc + d)); acc += d
        group, glen = [], 0
        for item in wt:
            group.append(item); glen += len(item[0]) + 1
            if len(group) >= 3 or glen >= 16 or item is wt[-1]:
                # ass-text: pop + jitter + keyword-highlight
                j = (hash(s["id"] + str(len(ev))) % 25) / 10 - 1.2
                fx = r"{\fscx62\fscy62" + (r"{\fr%.1f}" % j if jitter else "") + \
                     r"}".join([]) if False else r"{\fscx62\fscy62" + (r"\fr%.1f" % j if jitter else "") + \
                     r"\t(0,70,\fscx100\fscy100)\fad(35,45)}"
                parts = []
                for w, a, b in group:
                    clean = w.strip('.,!?"()').lower()
                    if clean in keywords:
                        parts.append(f"{RED}{w}{WHITE}")
                    else:
                        parts.append(w)
                ev.append((group[0][1], group[-1][2], fx + " ".join(parts)))
                group, glen = [], 0
    return ev

def parse_script(path=SCRIPT):
    blocks, cur = [], None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("###"):
            cur = {"id": line[3:].strip(), "text": ""}
            blocks.append(cur)
        elif line and cur is not None:
            cur["text"] += (" " if cur["text"] else "") + line
    return blocks

def main():
    blocks = parse_script()
    t = 0.0
    segs = []
    for b in blocks:
        p = os.path.join(AUDIO, f"{b['id']}.wav")
        if not os.path.exists(p):
            print("hoppar över (saknas wav):", b["id"]); continue
        d = wav_dur(p)
        segs.append({"id": b["id"], "text": b["text"], "start": round(t, 3), "dur": round(d, 3)})
        t += d + GAP
    total = t - GAP + TAIL
    json.dump({"segments": segs, "total": round(total, 3), "fps": 30},
              open(os.path.join(ROOT, "timings.json"), "w"), indent=1)
    print("total video:", round(total, 2), "s")

    ev = build_events(segs, load_keywords())
    lines = [f"Dialogue: 0,{ts(a)},{ts(b)},Pop,,0,0,0,,{txt}" for a, b, txt in ev]
    open(os.path.join(ROOT, "captions.ass"), "w", encoding="utf-8").write(HEADER + "\n".join(lines) + "\n")
    print("captions.ass:", len(ev), "events (v2 kinetic)")

if __name__ == "__main__":
    main()
