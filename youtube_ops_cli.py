from __future__ import annotations

import sys
from pathlib import Path

src = str(Path(__file__).resolve().parent / "src")
if src not in sys.path:
    sys.path.insert(0, src)

from youtube_intel.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
