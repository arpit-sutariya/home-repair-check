"""One diagnosis: safety first, then "what is it?", then everything else from rules.

Who decides what:
- Safety warnings: rules.hazards(), on the customer's words, before any model runs.
- What the problem probably is: the local models (or Claude, if there's an API key).
- Urgency, prices, quote verdict, the contractor message: rules.py and knowledge.json.
The AI never produces a price or decides whether something is safe.
"""
import base64
import os
import time

from . import config, models, rules

LOCATIONS = {
    "ceiling": ["water_stain", "mold", "wall_crack", "peeling_paint"],
    "wall": ["wall_crack", "water_stain", "mold", "peeling_paint"],
    "bathroom": ["mold", "water_stain", "plumbing_leak", "peeling_paint"],
    "kitchen or under a sink": ["plumbing_leak"],
    "basement or foundation": ["foundation_crack", "water_stain", "mold"],
    "roof or attic": ["roof_damage", "water_stain"],
    "outside wall": ["foundation_crack", "peeling_paint"],
    "outlet or switch": ["outlet_damage"],
}
CLAUDE_CONFIDENCE = {"high": 0.85, "medium": 0.6, "low": 0.35}


class InputError(ValueError):
    pass


def claude_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and config.MODE != "local"


def _combine(photo_p, text_p, location):
    """Average photo and description probabilities (equal weight, fixed before evaluation), then nudge by location."""
    if photo_p and text_p:
        p = {k: config.PHOTO_WEIGHT * photo_p[k] + (1 - config.PHOTO_WEIGHT) * text_p[k] for k in photo_p}
    else:
        p = dict(photo_p or text_p)
    for issue_id in LOCATIONS.get(location or "", []):
        p[issue_id] *= config.LOCATION_BOOST
    total = sum(p.values())
    return {k: v / total for k, v in p.items()}


def _breakdown(issues, final, photo_p=None, text_p=None, location=None):
    """Every problem's score from each signal, so the page can show how the answer was reached."""
    boosted = set(LOCATIONS.get(location or "", []))
    rows = [{"id": k, "name": issues[k]["name"], "final": round(final.get(k, 0.0), 3),
             "photo": round(photo_p[k], 3) if photo_p else None,
             "description": round(text_p[k], 3) if text_p else None,
             "location_boost": k in boosted} for k in issues]
    return sorted(rows, key=lambda r: -r["final"])


# ------------------------------------------------------------------ Claude (optional)
def _media_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


TOOL = {
    "name": "report_diagnosis",
    "description": "Report which listed home problem this most likely is.",
    "input_schema": {"type": "object", "properties": {
        "issue_id": {"type": "string", "description": "One of the listed ids, or 'unknown' if none fits."},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "runner_up": {"type": "string", "description": "Second most likely id, or 'none'."},
        "what_i_see": {"type": "string", "description": "One plain-English sentence on what the photo/description shows."},
        "safety_concern": {"type": "string", "description": "A specific safety risk you can see, or 'none'."}},
        "required": ["issue_id", "confidence", "runner_up", "what_i_see", "safety_concern"]},
}


def _claude(client, image: bytes | None, text: str, location: str | None, model: str | None = None):
    issues = rules.knowledge()["issues"]
    listing = "\n".join(f"- {i['id']}: {i['name']} ({i['symptoms']})" for i in issues)
    prompt = (f"A homeowner wants to know what this problem is.\nWhere: {location or 'not given'}\n"
              f"Their description: {text.strip() or '(none)'}\n\nPossible problems:\n{listing}\n\n"
              "Pick the closest id. Use 'low' confidence if the photo or description is unclear. "
              "Don't estimate prices; that's handled elsewhere.")
    content = []
    if image:
        media = _media_type(image)
        content.append({"type": "image", "source": {"type": "base64", "media_type": media,
                                                     "data": base64.b64encode(image).decode()}})
    content.append({"type": "text", "text": prompt})
    resp = client.messages.create(model=model or config.MODEL, max_tokens=400, tools=[TOOL],
                                  tool_choice={"type": "tool", "name": "report_diagnosis"},
                                  messages=[{"role": "user", "content": content}])
    out = next(b.input for b in resp.content if b.type == "tool_use")
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    return dict(out), usage


_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(max_retries=2, timeout=60)
    return _client


# ------------------------------------------------------------------ main entry
def diagnose(image: bytes | None, text: str = "", location: str | None = None, engine: str | None = None,
             photo_style: str = "cues", model: str | None = None) -> dict:
    t0 = time.perf_counter()
    text = (text or "")[: config.MAX_TEXT]
    if not image and not text.strip():
        raise InputError("Add a photo or describe the problem.")
    if location and location not in LOCATIONS:
        location = None
    engine = engine or ("claude" if claude_available() else "local")
    hazard_list = rules.hazards(text)  # safety comes from the customer's words, not from a model
    issues = rules.issues()
    usage, seen, errors = None, None, []
    photo_p = text_p = None
    probs = None
    if engine == "claude":
        try:
            out, usage = _claude(client(), image, text, location, model)
            pid = out["issue_id"] if out["issue_id"] in issues else None
            conf = CLAUDE_CONFIDENCE.get(out["confidence"], 0.35)
            probs = {k: 0.0 for k in issues}
            if pid:
                probs[pid] = conf
            if out.get("runner_up") in issues and out["runner_up"] != pid:
                probs[out["runner_up"]] = (1 - conf) * 0.8
            seen = out.get("what_i_see")
            concern = (out.get("safety_concern") or "").strip()
            if concern and concern.lower() != "none":
                hazard_list.append({"id": "model_flag", "title": "Possible safety concern",
                                    "steps": [concern, "If you're unsure, keep people away from it and ask a professional to check it first."]})
        except Exception as e:  # API problems: fall back to the local models rather than failing the customer
            errors.append(f"claude: {type(e).__name__}: {str(e)[:150]}")
            engine = "local"
    if engine == "local":
        photo_p = models.photo_probs(models.load_image(image), photo_style) if image else None
        text_p = models.text_probs(text) if text.strip() else None
        probs = _combine(photo_p, text_p, location)
        if photo_p:
            seen = "From the photo: " + ", ".join(
                f"{issues[k]['name'].lower()} ({v:.0%})" for k, v in sorted(photo_p.items(), key=lambda kv: -kv[1])[:2])

    ranked = sorted(probs.items(), key=lambda kv: -kv[1])
    breakdown = _breakdown(issues, probs, photo_p, text_p, location if engine == "local" else None)
    top_id, top_p = ranked[0]
    not_sure = top_p < config.NOT_SURE_BELOW
    issue = issues[top_id]
    sev = rules.severity(issue, text, hazard_list)
    tiers = rules.costs(issue, text)
    return {
        "engine": engine, "model": (model or config.MODEL) if engine == "claude" else None,
        "hazards": hazard_list,
        "issue": {"id": top_id, "name": issue["name"], "short": issue["short"], "confidence": round(top_p, 3)},
        "alternatives": [{"id": k, "name": issues[k]["name"], "confidence": round(v, 3)} for k, v in ranked[1:3] if v > 0],
        "not_sure": not_sure,
        "tell_apart": issue["tell_apart"] if not_sure else None,
        "seen": seen,
        "used": [x for x, on in (("photo", bool(image)), ("description", bool(text.strip())), ("location", bool(location))) if on],
        "severity": sev, "costs": tiers, "trade": issue["trade"], "diy": issue["diy"], "now": issue["now"],
        "questions": issue["questions"],
        "message": rules.contractor_message(issue, text, location, sev, bool(image)),
        "breakdown": breakdown, "thresholds": {"not_sure_below": config.NOT_SURE_BELOW},
        "usage": usage, "errors": errors, "latency_ms": round((time.perf_counter() - t0) * 1000),
    }
