import base64
import io
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from repaircheck import config, diagnose as dx


def png():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (180, 150, 110)).save(buf, "PNG")
    return buf.getvalue()


def test_needs_a_photo_or_description():
    with pytest.raises(dx.InputError):
        dx.diagnose(None, "   ")


def test_photo_and_description_are_combined(fake_models):
    fake_models["photo"] = fake_models["probs"]("mold", 0.6)
    fake_models["text"] = fake_models["probs"]("water_stain", 0.9)
    r = dx.diagnose(png(), "brown ring on the ceiling")
    assert r["issue"]["id"] == "water_stain" and r["used"] == ["photo", "description"]
    assert r["alternatives"][0]["id"] == "mold"


def test_location_nudges_the_answer(fake_models):
    p = fake_models["probs"]("water_stain", 0.3)
    p["outlet_damage"] = 0.28
    fake_models["text"] = p
    assert dx.diagnose(None, "something is wrong", location="outlet or switch")["issue"]["id"] == "outlet_damage"


def test_low_confidence_says_not_sure_and_asks(fake_models):
    fake_models["text"] = fake_models["probs"]("mold", 0.3)
    r = dx.diagnose(None, "weird spots")
    assert r["not_sure"] and r["tell_apart"]


def test_safety_warning_does_not_depend_on_the_model(fake_models):
    fake_models["text"] = fake_models["probs"]("peeling_paint", 0.99)  # model says "paint"...
    r = dx.diagnose(None, "paint is peeling and I smell gas")         # ...the gas warning still shows
    assert r["hazards"][0]["id"] == "gas" and r["severity"]["level"] == 5


class FakeClaude:
    def __init__(self, answer):
        self.answer, self.requests = answer, []
        self.messages = self

    def create(self, **kw):
        self.requests.append(kw)
        return NS(content=[NS(type="tool_use", input=self.answer)], usage=NS(input_tokens=1200, output_tokens=60))


def test_claude_picks_the_problem_but_code_sets_the_price(monkeypatch):
    fake = FakeClaude({"issue_id": "foundation_crack", "confidence": "high", "runner_up": "wall_crack",
                       "what_i_see": "A stair-step crack in brick.", "safety_concern": "none"})
    monkeypatch.setattr(dx, "client", lambda: fake)
    r = dx.diagnose(png(), "crack in the brick", engine="claude")
    assert r["engine"] == "claude" and r["issue"]["id"] == "foundation_crack"
    assert r["costs"][0]["source"].startswith("This Old House")  # from knowledge.json, not the model
    content = fake.requests[0]["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/png"
    assert fake.requests[0]["tool_choice"] == {"type": "tool", "name": "report_diagnosis"}


def test_claude_can_add_a_safety_warning_but_not_remove_one(monkeypatch):
    fake = FakeClaude({"issue_id": "outlet_damage", "confidence": "medium", "runner_up": "none",
                       "what_i_see": "Melted outlet.", "safety_concern": "The outlet looks melted."})
    monkeypatch.setattr(dx, "client", lambda: fake)
    r = dx.diagnose(None, "outlet sparks", engine="claude")
    assert {h["id"] for h in r["hazards"]} == {"electrical_fire", "model_flag"}


def test_claude_inventing_a_problem_type_is_ignored(monkeypatch):
    fake = FakeClaude({"issue_id": "termites", "confidence": "high", "runner_up": "mold",
                       "what_i_see": "?", "safety_concern": "none"})
    monkeypatch.setattr(dx, "client", lambda: fake)
    r = dx.diagnose(None, "holes in wood", engine="claude")
    assert r["issue"]["id"] == "mold" and r["not_sure"]


def test_api_failure_falls_back_to_local(monkeypatch, fake_models):
    def boom():
        raise RuntimeError("API down")
    monkeypatch.setattr(dx, "client", boom)
    r = dx.diagnose(None, "brown ring on the ceiling", engine="claude")
    assert r["engine"] == "local" and "API down" in r["errors"][0]


def test_web_api(fake_models):
    image = "data:image/png;base64," + base64.b64encode(png()).decode()
    with TestClient(main.app) as c:
        r = c.post("/api/diagnose", json={"image": image, "text": "brown ring", "location": "ceiling"}).json()
        assert r["issue"]["id"] == "water_stain" and r["costs"]
        q = c.post("/api/quote", json={"issue_id": "water_stain", "text": "brown ring", "amount": 900}).json()
        assert q["verdict"] == "typical"
        assert c.post("/api/diagnose", json={"text": ""}).status_code == 400
        assert c.post("/api/diagnose", json={"image": "data:image/png;base64,!!!"}).status_code == 400
        assert c.get("/").status_code == 200


def test_rate_limit(fake_models, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT", 2)
    main._rate.clear()
    with TestClient(main.app) as c:
        codes = [c.post("/api/diagnose", json={"text": "brown ring"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_breakdown_explains_every_problem(fake_models):
    fake_models["photo"] = fake_models["probs"]("mold", 0.6)
    fake_models["text"] = fake_models["probs"]("water_stain", 0.9)
    r = dx.diagnose(png(), "brown ring on the ceiling", location="ceiling")
    rows = {b["id"]: b for b in r["breakdown"]}
    assert len(rows) == 8 and r["breakdown"][0]["id"] == r["issue"]["id"]
    assert rows["mold"]["photo"] == 0.6 and rows["water_stain"]["description"] == 0.9
    assert rows["water_stain"]["location_boost"] and not rows["outlet_damage"]["location_boost"]
    assert abs(sum(b["final"] for b in r["breakdown"]) - 1) < 0.01


def test_safety_warning_says_which_words_triggered_it(fake_models):
    r = dx.diagnose(None, "I think I smell gas near the stove")
    assert r["hazards"][0]["matched"] == "smell gas"


def test_media_type_detection():
    assert dx._media_type(png()) == "image/png"
    assert dx._media_type(b"RIFF\0\0\0\0WEBPVP8 ") == "image/webp"
    assert dx._media_type(b"GIF89a...") == "image/gif"
    assert dx._media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"


def test_rate_limit_cant_be_dodged_with_a_fake_forwarded_for(fake_models, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT", 2)
    main._rate.clear()
    with TestClient(main.app) as c:
        codes = [c.post("/api/diagnose", json={"text": "brown ring"},
                        headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_rate_limit_forgets_idle_visitors(monkeypatch):
    main._rate.clear()
    monkeypatch.setattr(main, "_SWEEP_ABOVE", 3)
    old = main.time.time() - config.RATE_WINDOW_S - 1
    for i in range(5):
        main._rate[f"old-{i}"].append(old)
    main._rate_limit("new")
    assert set(main._rate) == {"new"}


def test_quote_rejects_bad_amounts(fake_models):
    with TestClient(main.app) as c:
        assert c.post("/api/quote", json={"issue_id": "water_stain", "amount": -5}).status_code == 422
        assert c.post("/api/quote", json={"issue_id": "water_stain", "amount": 1e12}).status_code == 422
        assert c.post("/api/quote", json={"issue_id": "nope", "amount": 100}).status_code == 404


def test_evals_page_and_data():
    with TestClient(main.app) as c:
        assert c.get("/evals").status_code == 200
        d = c.get("/api/evals").json()
        assert {"photos", "descriptions", "safety", "safety_heldout"} <= set(d)
        assert c.get("/api/meta").json()["problems"][0]["id"] == "water_stain"
