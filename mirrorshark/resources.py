"""Locate bundled data files (user guide) both from source and from the packaged exe."""
import sys
from pathlib import Path


def find_resource(rel: str) -> Path | None:
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        roots.append(Path(sys.executable).parent)
    here = Path(__file__).resolve().parent
    roots += [here.parent, here]
    for r in roots:
        p = r / rel
        if p.exists():
            return p
    return None
