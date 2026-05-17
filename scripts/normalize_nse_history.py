import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.transformation.normalize_nse_history import normalize_nse_history


if __name__ == "__main__":
    normalize_nse_history()