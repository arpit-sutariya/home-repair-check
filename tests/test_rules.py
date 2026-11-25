import json
from pathlib import Path

import pytest

from repaircheck import rules

EVAL = Path(__file__).resolve().parent.parent / "eval"


def _cases(name):
    return json.loads((EVAL / name).read_text())


# Every emergency and near-miss from both eval sets is a permanent regression test.
@pytest.mark.parametrize("case", _cases("safety_cases.json")["positives"] + _cases("safety_heldout.json")["positives"],
                         ids=lambda c: c["text"][:40])
def test_emergencies_get_the_right_warning(case):
    assert case["hazard"] in {h["id"] for h in rules.hazards(case["text"])}


@pytest.mark.parametrize("case", _cases("safety_cases.json")["negatives"] + _cases("safety_heldout.json")["negatives"],
                         ids=lambda c: c["text"][:40])
def test_near_misses_get_no_warning(case):
    assert rules.hazards(case["text"]) == []


def test_every_price_has_a_source():
    for issue in rules.knowledge()["issues"]:
        assert issue["tiers"]
        for t in issue["tiers"]:
            assert 0 < t["low"] < t["high"] and t["source"] and t["url"].startswith("https://")
            if t.get("typical"):
                assert t["low"] <= t["typical"] <= t["high"]


def test_conditional_price_tiers():
    stain = rules.issues()["water_stain"]
    assert [t["name"] for t in rules.costs(stain, "small brown ring")] == ["Fix the leak (plumbing)", "Repair water-damaged drywall"]
    big = rules.costs(stain, "the whole ceiling is soaked")
    assert any("Larger water damage" in t["name"] and t["why"] for t in big)


def test_urgency_goes_up_with_warning_words_and_hazards():
    crack = rules.issues()["wall_crack"]
    assert rules.severity(crack, "hairline crack", [])["level"] == 2
    assert rules.severity(crack, "crack is getting bigger and the door sticks", [])["level"] == 3
    assert rules.severity(crack, "crack", [{"id": "gas"}])["level"] == 5


@pytest.mark.parametrize("amount,verdict", [(20, "low"), (100, "typical"), (900, "typical"), (2000, "high"), (5000, "very_high")])
def test_quote_verdict(amount, verdict):
    tiers = rules.costs(rules.issues()["water_stain"], "brown stain")  # $50-$800 + $300-$850
    assert rules.quote_verdict(amount, tiers)["verdict"] == verdict


def test_structural_advice_only_for_structural_problems():
    stain = rules.quote_verdict(9000, rules.costs(rules.issues()["water_stain"], ""), structural=False)
    found = rules.quote_verdict(30000, rules.costs(rules.issues()["foundation_crack"], ""), structural=True)
    assert "engineer" not in stain["message"] and "engineer" in found["message"]


def test_contractor_message_quotes_the_customer_and_lists_questions():
    issue = rules.issues()["mold"]
    msg = rules.contractor_message(issue, "black spots in the shower", "bathroom", None, True)
    assert '"black spots in the shower"' in msg and "attached a photo" in msg
    assert all(q in msg for q in issue["questions"])
