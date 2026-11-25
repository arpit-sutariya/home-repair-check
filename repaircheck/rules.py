"""The parts that must be right every time, so they're plain code, not AI:
safety warnings, urgency, price ranges, and the quote verdict."""
import json
import re
from functools import lru_cache
from pathlib import Path

URGENCY = {
    1: ("Can wait", "Cosmetic. Fix it when convenient."),
    2: ("Plan it", "Not urgent, but keep an eye on it and fix it in the next few months."),
    3: ("Fix within a few weeks", "It can get worse or cause other damage if it's left."),
    4: ("Fix this week", "Likely to get worse quickly or cause bigger damage."),
    5: ("Act now", "A safety risk. Deal with it today, and follow any safety steps shown first."),
}


@lru_cache(maxsize=1)
def knowledge() -> dict:
    return json.loads((Path(__file__).parent / "knowledge.json").read_text())


@lru_cache(maxsize=1)
def issues() -> dict:
    return {i["id"]: i for i in knowledge()["issues"]}


def _norm(text: str) -> str:
    return " " + re.sub(r"\s+", " ", (text or "").lower()) + " "


@lru_cache(maxsize=1)
def _hazard_patterns():
    return [(h, [re.compile(p, re.I) for p in h["patterns"]]) for h in knowledge()["hazards"]]


# Phrases that mention a hazard word without describing a hazard.
_NOT_HAZARD = re.compile(r"no smoke|no sparks|not sparking|never sparked|not overflowing|burn(ed|t) (some )?(popcorn|toast|food)", re.I)


def hazards(text: str) -> list[dict]:
    """Safety warnings from the customer's own words. Runs before and regardless of any AI."""
    t = _NOT_HAZARD.sub(" ", _norm(text))
    found = []
    for h, pats in _hazard_patterns():
        m = next((m for p in pats if (m := p.search(t))), None)
        if m:  # "matched" shows the customer which of their words triggered the warning
            found.append({"id": h["id"], "title": h["title"], "steps": h["steps"], "matched": m.group(0).strip()})
    return found


def _mentions(text: str, words) -> list[str]:
    t = _norm(text)
    return [w for w in words if re.search(r"(?<![a-z])" + re.escape(w.lower()) + r"(?![a-z])", t)]


def severity(issue: dict, text: str, hazard_list: list) -> dict:
    level = issue["base_severity"]
    reasons = []
    worse = _mentions(text, issue["worse_if"])
    if worse:
        level += 1
        reasons.append("you mentioned " + ", ".join(f'"{w}"' for w in worse[:3]))
    if hazard_list:
        level = 5
        reasons.append("a safety risk in your description")
    level = max(1, min(5, level))
    label, meaning = URGENCY[level]
    return {"level": level, "label": label, "meaning": meaning, "reasons": reasons}


def costs(issue: dict, text: str) -> list[dict]:
    """Every tier without a 'when' applies; tiers with 'when' apply only if the description mentions one."""
    out = []
    for tier in issue["tiers"]:
        hits = _mentions(text, tier.get("when", []))
        if "when" in tier and not hits:
            continue
        out.append({k: tier[k] for k in ("name", "low", "high", "source", "url")} |
                   {"typical": tier.get("typical"), "why": f'you mentioned "{hits[0]}"' if hits else None})
    return out


def quote_verdict(amount: float, tiers: list[dict], structural: bool = False) -> dict:
    """Compare a contractor's quote with the typical ranges. Ranges are national, so this is a sanity check."""
    if not tiers or amount is None or amount <= 0:
        return {"verdict": "unknown", "message": "Enter the quote's total in dollars."}
    total_low = sum(t["low"] for t in tiers)
    total_high = sum(t["high"] for t in tiers)
    best = min(tiers, key=lambda t: 0 if t["low"] <= amount <= t["high"] else min(abs(amount - t["low"]), abs(amount - t["high"])))
    lo, hi = min(t["low"] for t in tiers), total_high
    if amount < lo * 0.6:
        v, msg = "low", ("This is well below the usual range. Ask exactly what's included: a very low quote can "
                         "skip fixing the cause or add charges later.")
    elif amount <= hi:
        v, msg = "typical", f"This is within the usual range for {best['name'].lower()}."
    elif amount <= hi * 1.5:
        v, msg = "high", ("This is above the usual range. Ask for an itemized quote and get one or two more "
                          "bids; extra work may be justified, but it should be explained.")
    else:
        v, msg = "very_high", ("This is far above the usual range. Get at least two more quotes and ask exactly what's "
                               "included. If they found more damage than you can see, ask them to show you.")
    if structural and v in ("high", "very_high"):
        msg += " For structural work, an independent structural engineer's opinion is worth getting before you sign."
    return {"verdict": v, "message": msg, "closest": best["name"], "range": [lo, hi],
            "all_tiers_total": [total_low, total_high]}


def contractor_message(issue: dict, text: str, location: str | None, sev: dict, has_photo: bool) -> str:
    where = f" ({location})" if location else ""
    described = f'\n\nWhat I\'m seeing: "{text.strip()[:400]}"' if text and text.strip() else ""
    photo = "\nI've attached a photo." if has_photo else ""
    asks = "\n".join(f"- {q}" for q in issue["questions"])
    return (f"Hi, I need help with a problem at home. It looks like {issue['phrase']}{where}.{described}{photo}\n\n"
            f"How soon could you take a look, and could you send an itemized quote? I'd also like to know:\n{asks}\n\nThanks!")
