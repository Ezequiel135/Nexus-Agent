#!/usr/bin/env python3
"""
Archived compatibility launcher.
Preferred entrypoint remains the repository root launcher.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_LAUNCHER = PROJECT_ROOT.parent / "pc_remote_unified.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    if ROOT_LAUNCHER.exists():
        code = compile(ROOT_LAUNCHER.read_text(encoding="utf-8"), str(ROOT_LAUNCHER), "exec")
        exec(code, {"__name__": "__main__"})
