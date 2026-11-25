import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

RUNTIME = Path(os.environ.get("REPAIR_RUNTIME", ROOT / "runtime"))
MODEL_CACHE = Path(os.environ.get("MODEL_CACHE", RUNTIME / "models"))
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
# "auto" = Claude when ANTHROPIC_API_KEY is set, otherwise the local models.
MODE = os.environ.get("DIAGNOSIS_MODE", "auto")
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_TEXT = 1500
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "20"))          # diagnoses per visitor...
RATE_WINDOW_S = int(os.environ.get("RATE_WINDOW_S", "600"))   # ...per 10 minutes
WARM_MODELS = os.environ.get("WARM_MODELS", "on").lower() not in ("off", "0", "false")

# Decision settings, fixed before evaluation.
NOT_SURE_BELOW = 0.45        # below this, show the top two possibilities and a question to tell them apart
PHOTO_WEIGHT = 0.5           # when there's a photo AND a description, average them equally
LOCATION_BOOST = 1.5         # "where is it?" nudges matching problems up
TEXT_SCALE = 50.0            # softmax temperature for description similarity
CLIP_SCALE = 100.0           # CLIP's own temperature
