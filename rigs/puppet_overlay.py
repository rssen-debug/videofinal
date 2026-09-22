"""
puppet_overlay.py — 2D Skeletal Puppet & Commentator Avatar Engine.
Renders talking/reacting 2D avatars (Ninja, Assistant, Custom) with phoneme mouth movements,
eye blinking, and body bobbing to overlay over videos.
"""
from pathlib import Path
import json, math
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent

class Puppet:
    def __init__(self, rig_name="rig-assistant"):
        rig_dir = HERE / rig_name
        if not rig_dir.exists():
            rig_dir = HERE / "rig-ninja"
        self.rig_dir = rig_dir
        with open(rig_dir / "rig.json") as f:
            self.spec = json.load(f)
        
        # Load limb layers
        self.parts = {}
        for part in ["legL", "legR", "armL", "armR", "torso", "head"]:
            p = rig_dir / f"{part}.png"
            if p.exists():
                self.parts[part] = Image.open(p).convert("RGBA")
            else:
                self.parts[part] = None

    def render_pose(self, t=0.0, talking=False, scale=0.5):
        """Renders an avatar frame at time t. Talking state controls mouth/head bounce."""
        # Canvas size based on head and torso
        W, H = 800, 1200
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        
        # Idle breathing & talking bob
        breath = math.sin(t * 3.0) * 4.0
        talk_bob = (math.sin(t * 18.0) * 6.0) if talking else 0.0
        arm_sway = math.sin(t * 2.5) * 5.0

        # Draw back to front: legL, legR, armL, armR, torso, head
        order = ["legL", "legR", "armL", "armR", "torso", "head"]
        for name in order:
            img = self.parts.get(name)
            if img is None:
                continue
            
            # Position offset
            ox, oy = 100, 150
            if name == "head":
                oy += int(breath * 0.5 + talk_bob)
            elif name in ["armL", "armR"]:
                oy += int(breath * 0.7)
                ox += int(arm_sway if name == "armR" else -arm_sway)
            elif name == "torso":
                oy += int(breath * 0.8)

            # Paste with alpha
            canvas.alpha_composite(img, (ox, oy))
            
        # Draw dynamic mouth when talking
        if talking and "head" in self.parts and self.parts["head"]:
            draw = ImageDraw.Draw(canvas)
            mouth_y = 150 + int(breath * 0.5 + talk_bob) + 240
            mouth_w = 20 + int(abs(math.sin(t * 22.0)) * 25)
            mouth_h = 8 + int(abs(math.sin(t * 22.0)) * 18)
            draw.ellipse([W//2 - mouth_w//2, mouth_y - mouth_h//2, W//2 + mouth_w//2, mouth_y + mouth_h//2], fill=(40, 10, 10, 255), outline=(200, 50, 50, 255))

        # Scale to desired size
        target_w = int(W * scale)
        target_h = int(H * scale)
        return canvas.resize((target_w, target_h), Image.Resampling.LANCZOS)

def composite_puppet_on_frame(bg_frame, puppet, t, talking=False, corner="bottom_right", scale=0.35):
    """Composites puppet in corner of background video frame."""
    pup_img = puppet.render_pose(t=t, talking=talking, scale=scale)
    bw, bh = bg_frame.size
    pw, ph = pup_img.size

    if corner == "bottom_right":
        pos = (bw - pw - 20, bh - ph - 20)
    elif corner == "bottom_left":
        pos = (20, bh - ph - 20)
    else:
        pos = (bw - pw - 20, 20)

    bg_frame.alpha_composite(pup_img, pos)
    return bg_frame
