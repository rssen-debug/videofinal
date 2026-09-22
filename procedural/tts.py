# -*- coding: utf-8 -*-
"""
tts.py – Text till tal.

Backends (väljs automatiskt i turordning om backend="auto"):
  gtts    – Google Translate-röst via nätet. Bra kvalitet, gratis, stödjer svenska.
  espeak  – Offline (espeak-ng / espeak måste vara installerat). Robotiskt men funkar.
  none    – Ingen röst: video med undertexter + musik.
"""
import contextlib
import shutil
import subprocess
import wave


def wav_seconds(path):
    with contextlib.closing(wave.open(str(path), "rb")) as w:
        return w.getnframes() / float(w.getframerate())


def read_wav_float(path):
    import numpy as np
    with contextlib.closing(wave.open(str(path), "rb")) as w:
        frames = w.readframes(w.getnframes())
        ch = w.getnchannels()
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data


def estimate_dur(text):
    return max(2.2, 0.5 + len(text.split()) * 0.42)


def _gtts_one(text, lang, mp3_path, wav_path, ffmpeg):
    from gtts import gTTS
    gTTS(text=text, lang=lang).save(str(mp3_path))
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(mp3_path),
                    "-ac", "1", "-ar", "44100", str(wav_path)], check=True)
    return wav_seconds(wav_path)


def _espeak_one(exe, text, lang, wav_path):
    subprocess.run([exe, "-v", lang, "-s", "145", "-w", str(wav_path), text], check=True)
    return wav_seconds(wav_path)


def synth_lines(texts, lang, outdir, ffmpeg, backend="auto"):
    """Syntetiserar varje replik. Returnerar ([(wav_path|None, dur), ...], backend)."""
    order = [backend] if backend != "auto" else ["gtts", "espeak", "none"]
    wavs = []
    for b in order:
        wavs = []
        ok = True
        if b == "none":
            return [(None, estimate_dur(t)) for t in texts], "none"
        if b == "espeak" and not (shutil.which("espeak-ng") or shutil.which("espeak")):
            continue
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        for i, text in enumerate(texts):
            wav_path = outdir / f"line_{i:02d}.wav"
            try:
                if b == "gtts":
                    dur = _gtts_one(text, lang, outdir / f"line_{i:02d}.mp3", wav_path, ffmpeg)
                else:
                    dur = _espeak_one(exe, text, lang, wav_path)
                wavs.append((wav_path, dur))
            except Exception as e:  # noqa: BLE001 - prova nästa backend
                print(f"  [tts] {b} misslyckades ({e}) – provar nästa...")
                ok = False
                break
        if ok:
            return wavs, b
    return [(None, estimate_dur(t)) for t in texts], "none"
