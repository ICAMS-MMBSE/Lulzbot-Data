import sys
from pathlib import Path

# Allow running pytest from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
