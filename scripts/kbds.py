#!/usr/bin/env python3
"""Repository entrypoint; canonical implementation is bundled in the skill."""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    scripts = Path(__file__).resolve().parents[1] / "skills/kbds-data-organizer/scripts"
    command = sys.argv[1:2]
    if command == ["self-check"]:
        if len(sys.argv) != 2:
            raise SystemExit("self-check accepts no arguments")
        script = scripts / "self_check.py"
        sys.argv.pop(1)
    elif command == ["report"]:
        script = scripts / "build_html_report.py"
        sys.argv.pop(1)
    else:
        script = scripts / "toolkit.py"
    sys.path.insert(0, str(scripts))
    runpy.run_path(str(script), run_name="__main__")
