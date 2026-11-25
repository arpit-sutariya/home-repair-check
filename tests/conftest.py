import os
import tempfile

os.environ["REPAIR_RUNTIME"] = tempfile.mkdtemp(prefix="rc-test-")
os.environ["WARM_MODELS"] = "off"          # never download the real models from tests
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402

from repaircheck import models  # noqa: E402


@pytest.fixture()
def fake_models(monkeypatch):
    """Stand-ins for CLIP and the text model: fixed probabilities, no downloads."""
    from repaircheck import rules
    ids = list(rules.issues())

    def probs(top, p):
        rest = (1 - p) / (len(ids) - 1)
        return {i: (p if i == top else rest) for i in ids}

    state = {"photo": probs("water_stain", 0.7), "text": probs("water_stain", 0.8)}
    monkeypatch.setattr(models, "photo_probs", lambda img, style="cues": state["photo"])
    monkeypatch.setattr(models, "text_probs", lambda text: state["text"])
    state["probs"] = probs
    return state
