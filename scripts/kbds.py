#!/usr/bin/env python3
"""Repository entrypoint; canonical implementation is bundled in the skill."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    script = Path(__file__).resolve().parents[1] / ".agents/skills/kbds-data-organizer/scripts/toolkit.py"
    runpy.run_path(str(script), run_name="__main__")
