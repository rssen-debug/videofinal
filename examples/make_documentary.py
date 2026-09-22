#!/usr/bin/env python3
"""Example: Generate a 16:9 Cinema Documentary."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from videofinal import run_documentary

if __name__ == "__main__":
    topic = "The Rise and Fall of Offline Streamers"
    print(f"Creating documentary for: {topic}")
    run_documentary(topic, dry_run=False)
