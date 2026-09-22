"""
vertical_engine.py — High-Retention 9:16 Vertical Video Engine (Shorts, TikTok, Reels).
Combines split-screen reaction compositing, dynamic karaoke captions,
sidechain audio ducking, and procedural ambient audio bed.
"""
import os, sys, math, json, wave, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

SR = 44100
FPS = 30
W_DEFAULT = 720
H_DEFAULT = 1280

def synthesize_ambient_bed(duration, sr=SR, mood="dark_piano"):
    """Synthesizes a minimal, royalty-free dark ambient piano/synth bed without external files."""
    D = math.ceil(duration)
    total_samples = int(D * sr)
    music = np.zeros(total_samples, dtype=np.float32)
    beat = 60.0 / 72.0

    def hz(m): return 440.0 * 2.0 ** ((m - 69.0) / 12.0)

    def piano_note(midi, dur, amp):
        t = np.arange(int(dur * sr)) / sr
        f = hz(midi)
        a = np.zeros(len(t), dtype=np.float32)
        for harmonic, weight in [(1, 1.0), (2, 0.30), (3, 0.16), (4, 0.055), (6, 0.018)]:
            a += weight * np.sin(2 * np.pi * f * harmonic * (1 + 0.00005 * harmonic) * t) * np.exp(-t * (0.85 + 0.26 * harmonic))
        a *= np.minimum(1.0, t / 0.012) * np.minimum(1.0, (dur - t) / 0.18)
        return (amp * a).astype(np.float32)

    progression = [[50, 57, 60, 64], [46, 53, 57, 60], [43, 50, 57, 58], [45, 52, 55, 62]]
    for bar, st in enumerate(np.arange(0, D, beat * 8)):
        chord = progression[bar % 4]
        dur = beat * 10
        t = np.arange(int(dur * sr)) / sr
        env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.7
        pad = np.zeros(len(t), dtype=np.float32)
        for midi in chord:
            f = hz(midi)
            pad += (np.sin(2 * np.pi * f * t) + 0.33 * np.sin(2 * np.pi * f * 1.002 * t)) / len(chord)
        
        idx = int(st * sr)
        n = min(len(pad), total_samples - idx)
        if idx >= 0 and n > 0:
            music[idx:idx + n] += (0.08 * pad[:n] * env[:n]).astype(np.float32)
            
        for off, note, vel in [(0, chord[0] + 12, 0.09), (2.5, chord[2] + 12, 0.06), (5, chord[3] + 12, 0.05)]:
            note_a = piano_note(note, 4.0, vel)
            n_idx = int((st + off * beat) * sr)
            n_len = min(len(note_a), total_samples - n_idx)
            if n_idx >= 0 and n_len > 0:
                music[n_idx:n_idx + n_len] += note_a[:n_len]

    peak = max(float(np.max(np.abs(music))), 1e-6)
    if peak > 0.95:
        music = music * (0.95 / peak)
    return music

def render_vertical_frame(base_bg, top_img=None, bottom_img=None, text_words=None, current_time=0.0, width=720, height=1280):
    """Composites a single 9:16 vertical frame with optional split screens and active word pop."""
    canvas = Image.new("RGBA", (width, height), (15, 17, 21, 255))
    draw = ImageDraw.Draw(canvas)

    # 1. Background fill or blurred background
    if base_bg is not None:
        bg_resized = base_bg.resize((width, height), Image.Resampling.LANCZOS)
        bg_blurred = bg_resized.filter(ImageFilter.GaussianBlur(15))
        canvas.paste(bg_blurred, (0, 0))
    
    # 2. Split panes
    if top_img is not None and bottom_img is not None:
        # Top Pane: (0, 80, width, height/2 - 20)
        pane_h = int(height * 0.42)
        t_crop = ImageOps.fit(top_img, (width - 40, pane_h), Image.Resampling.LANCZOS)
        canvas.paste(t_crop, (20, 90))
        # Divider or border
        draw.rectangle([18, 88, width - 20, 90 + pane_h], outline=(255, 215, 0, 180), width=3)

        # Bottom Pane: (20, height/2 + 20, width - 40, pane_h)
        b_top = int(height * 0.52)
        b_crop = ImageOps.fit(bottom_img, (width - 40, pane_h), Image.Resampling.LANCZOS)
        canvas.paste(b_crop, (20, b_top))
        draw.rectangle([18, b_top - 2, width - 20, b_top + pane_h], outline=(100, 200, 255, 180), width=3)
    elif top_img is not None:
        # Single full vertical centered crop
        c_crop = ImageOps.fit(top_img, (width, int(height * 0.75)), Image.Resampling.LANCZOS)
        canvas.paste(c_crop, (0, int(height * 0.12)))

    # 3. Dynamic Subtitles (Word-by-word active highlight)
    if text_words:
        # Find active chunk
        active_window = [w for w in text_words if w['start'] - 0.5 <= current_time <= w['end'] + 0.5]
        if active_window:
            full_line = " ".join([w['text'] for w in active_window[:4]])
            font = ImageFont.load_default()
            y_pos = int(height * 0.78)
            draw.rectangle([30, y_pos - 10, width - 30, y_pos + 50], fill=(0, 0, 0, 190), outline=(255, 215, 0, 200), width=2)
            draw.text((width // 2, y_pos + 12), full_line, fill=(255, 255, 255, 255), anchor="mm", font=font)

    return canvas
