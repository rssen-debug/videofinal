#!/usr/bin/env python3
"""Example: Generate a 9:16 Vertical Viral Short."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from videofinal import run_short

if __name__ == "__main__":
    topic = "Kai Cenat Reaction"
    print(f"Creating vertical short for: {topic}")
    run_short(topic, dry_run=False)
