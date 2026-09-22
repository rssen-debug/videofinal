#!/usr/bin/env python3
"""Example: Generate a 100% CPU Procedural Pixel Anime Episode."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from videofinal import run_procedural_episode

if __name__ == "__main__":
    print("Rendering procedural episode...")
    run_procedural_episode(seed=99, story_id=1, output="procedural_example.mp4")
