#!/usr/bin/env python3
"""engine/audio.py — TTS (edge-tts, offline/fri) + musikintensitet + SFX-budget.

HÖRNAN:  --voice en-GB-RyanNeural (lugn brittisk maskulin berättarröst),
          --voice auto → provar Ryan -> Thomas -> en-US-Andrew -> piper (om installerad).
Voiceovern mäts sedan -> timeline byggs runt VERKLIG duration.

Musik: engine söker lokala spår i assets/music/ (royalty-free). Fallback =
cinema.MUSIC_BEAT (syntetisk drone+beat, 0 copyright) med intensity->volym.
"""
import os, asyncio, subprocess, sys, json, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "audio")
MUSIC_DIR = os.path.join(ROOT, "assets", "music")

INTENSITY_VOL = {"LOW": 0.22, "MEDIUM": 0.30, "HIGH": 0.36, "IMPACT": 0.40}

def _ffmpeg():
    from research import sources
    return sources.ensure_ffmpeg()

def wav_dur(p):
    with wave.open(p, "rb") as w:
        return w.getnframes() / w.getframerate()

def _edge_tts(voice, text, out_wav):
    import edge_tts
    tmp = out_wav + ".mp3"

    async def go():
        await edge_tts.Communicate(text, voice).save(tmp)
    asyncio.run(go())
    subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", tmp, "-ac", "1",
                    "-ar", "44100", out_wav], check=True)
    os.remove(tmp) if os.path.exists(tmp) else None

def _piper(voice, text, out_wav):
    # optional fallback: piper TTS CLI (om installerat)
    binp = subprocess.run(["bash", "-c", "command -v piper"],
                          capture_output=True).returncode == 0
    if not binp:
        raise RuntimeError("piper saknas")
    r = subprocess.run(["bash", "-c", f"echo '{text}' | piper -m en_GB-alan-medium "
                        f"-f - > {out_wav}"], capture_output=True, text=True,
                       shell=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])

VOICE_FALLBACKS = ["en-GB-RyanNeural", "en-GB-ThomasNeural",
                   "en-US-AndrewNeural", "en-US-ChristopherNeural"]

def _text_tag(text, voice):
    import hashlib
    return hashlib.md5((text + "|" + voice).encode("utf-8")).hexdigest()[:16]

def synth(text, out_id, voice="auto", rate=None, cache=True):
    """Syntetiserar <out_id>.wav i audio/. Returnerar (path, duration_s).

    Cache är INNEHÅLLS-baserad: byts texten eller rösten så syntetiseras om
    (förhindrar gammal voiceover från tidigare ämnen)."""
    os.makedirs(AUDIO, exist_ok=True)
    out = os.path.join(AUDIO, f"{out_id}.wav")
    tag_path = os.path.join(AUDIO, f".{out_id}.tag")
    tag = _text_tag(text, voice)
    if cache and os.path.exists(out) and os.path.getsize(out) > 0:
        if os.path.exists(tag_path) and open(tag_path, encoding="utf-8").read().strip() == tag:
            return out, wav_dur(out)
    # rate/prosody: enkelt stöd för långsammare avslut
    if rate and voice != "auto" and False:  # edge-tts rate via ssml — hoppar (enkelhet)
        pass
    errors = []
    if voice in ("auto", "edge"):
        for v in VOICE_FALLBACKS:
            try:
                _edge_tts(v, text, out)
                open(tag_path, "w", encoding="utf-8").write(tag)
                return out, wav_dur(out)
            except Exception as e:
                errors.append(f"{v}: {str(e)[:120]}")
    else:
        try:
            _edge_tts(voice, text, out)
            open(tag_path, "w", encoding="utf-8").write(tag)
            return out, wav_dur(out)
        except Exception as e:
            errors.append(str(e)[:200])
    try:
        _piper(voice, text, out)
        open(tag_path, "w", encoding="utf-8").write(tag)
        return out, wav_dur(out)
    except Exception as e:
        errors.append(str(e)[:200])
    raise RuntimeError("TTS misslyckades (alla motorer): " + " | ".join(errors))

def local_music():
    """Lista av lokala spår i assets/music/ (mp3/wav/m4a/ogg)."""
    os.makedirs(MUSIC_DIR, exist_ok=True)
    out = []
    for f in sorted(os.listdir(MUSIC_DIR)):
        if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".opus")):
            out.append(os.path.join(MUSIC_DIR, f))
    return out

def music_segments(music_plan, total):
    """music_plan: [{from_block|from, intensity, duck_under_clips}] →
    lista av (time, intensity, label) för ffmpeg-volume-uttryck."""
    segs = []
    # svep block->absolut via timings om tillgängligt
    timings = None
    tp = os.path.join(ROOT, "timings.json")
    if os.path.exists(tp):
        try:
            timings = {s["id"]: s["start"]
                       for s in json.load(open(tp))["segments"]}
        except Exception:
            timings = None
    for m in music_plan or []:
        t = m.get("from", 0)
        if isinstance(t, str) and timings:
            t = timings.get(t, 0)
        segs.append((float(t), m.get("intensity", "MEDIUM")))
    if not segs:
        segs = [(0.0, "MEDIUM")]
    return segs
