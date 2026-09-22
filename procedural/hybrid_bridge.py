"""
hybrid_bridge.py — Procedural Animation Cutaways & SFX Injector.
Provides easy procedural scene generation and sound synthesis for insertion
into documentary timelines and short-form videos.
"""
import os, sys, math, random, wave
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from . import v2engine as V2
from . import music as MUS
from . import sfx as SFX

def render_procedural_cutaway(duration=3.0, fps=30, scene_type="action", title="DRAMA ALERT"):
    """
    Renders a sequence of PIL images (frames) for a procedural anime cutaway.
    """
    total_frames = int(duration * fps)
    frames = []

    for f in range(total_frames):
        t = f / fps
        im = Image.new("RGBA", (V2.W, V2.H), (15, 12, 24, 255))
        d = ImageDraw.Draw(im)
        
        # Grid/ground effect
        for gy in range(120, V2.H, 10):
            col = (40, 35, 60, 255)
            d.line([(0, gy), (V2.W, gy)], fill=col)
            
        # Draw dynamic procedural background elements
        if scene_type == "action":
            # Speedlines and bursts
            V2.speedlines(im, V2.W // 2, V2.H // 2, n=16, col=(255, 220, 100, 150))
            if t > 0.8:
                V2.impact_flash(im, 0.8, t)
        else:
            # Mystery portal
            V2.portal(im, V2.W // 2, V2.H // 2 + 10, t, seed=42)
            
        # Dramatic Title Banner
        banner = V2.ptext(title, scale=3, col=(255, 235, 60))
        bx = (V2.W - banner.width) // 2
        by = 25 + int(math.sin(t * 8.0) * 3.0)
        im.alpha_composite(banner, (bx, by))
        
        # Subtitle punchline
        sub = V2.ptext("EVIDENCE DETECTED", scale=1, col=(200, 220, 255))
        im.alpha_composite(sub, ((V2.W - sub.width) // 2, by + banner.height + 6))

        # Scale x4 to standard 1280x720
        out_frame = im.resize((1280, 720), Image.Resampling.NEAREST)
        frames.append(out_frame)

    return frames

def synthesize_cutaway_audio(duration=3.0, out_path="/tmp/cutaway_audio.wav"):
    """Synthesizes procedural 8-bit sound effects + sting for the cutaway."""
    sr = 44100
    n = int(sr * duration)
    mix = np.zeros(n, dtype=np.float32)

    # Add mystery/action motif
    m = MUS.section("action", duration, seed=42)
    m_len = min(len(m), n)
    mix[:m_len] += m[:m_len] * 0.7

    # Add whoosh impact
    whoosh = SFX.whoosh()
    w_len = min(len(whoosh), n)
    mix[:w_len] += whoosh[:w_len] * 0.5

    peak = max(float(np.max(np.abs(mix))), 1e-6)
    if peak > 0.92:
        mix *= 0.92 / peak
        
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return out_path
