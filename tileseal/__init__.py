"""TileSeal product package. Behaviour is the root grd module."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import grd  # noqa: E402
import grd_geometry  # noqa: E402

__all__ = ["grd", "grd_geometry"]
