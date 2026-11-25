"""Evaluation.

  python -m eval.run_eval            # local models (no API key)
  python -m eval.run_eval --claude   # also Claude (needs ANTHROPIC_API_KEY; ~75 vision calls + 48 text calls)

1. Photos (75 real photos, 5 problem types): which problem is it?
   Compares plain prompts ("a photo of mold growth") with the visual cues written in knowledge.json,
   to measure what that written-down domain knowledge is worth.
2. Descriptions (48 homeowner descriptions, 8 problem types).
3. Safety: do the hard-coded safety rules catch every emergency without crying wolf?
   First set: 30 emergencies + 30 near-misses (the rules were broadened after it showed misses).
   Held-out set: 20 + 20, written before re-running, never tuned on.
"""
import argparse
import io
import json
import os
import statistics
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from repaircheck import config, diagnose as dx, models, rules

HERE = Path(__file__).parent
PHOTOS = config.ROOT / "runtime" / "eval-photos"


def fetch_photos(cases):
    PHOTOS.mkdir(parents=True, exist_ok=True)
    missing = [c for c in cases["photos"] if not (PHOTOS / c["file"]).exists()]
    if not missing:
        return
    url = f"https://huggingface.co/datasets/{cases['dataset']}/resolve/main/{cases['archive']}"
    print(f"Downloading test photos ({len(missing)} missing, one ~40 MB archive)...")
    with urllib.request.urlopen(url, timeout=300) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    for c in missing:
        name = c["source"].split(":", 1)[1]
        (PHOTOS / c["file"]).write_bytes(z.read(name))


def calibration(rows, bins=5):
    """Expected calibration error: how far stated confidence is from actual accuracy (0 = perfectly honest).
    Also returns the reliability bins for plotting."""
    out, ece = [], 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        inb = [r for r in rows if lo <= r["conf"] < hi or (b == bins - 1 and r["conf"] == 1.0)]
        if not inb:
            continue
        conf = statistics.mean(r["conf"] for r in inb)
        acc = sum(r["top"] == r["label"] for r in inb) / len(inb)
        ece += len(inb) / len(rows) * abs(acc - conf)
        out.append({"range": [round(lo, 2), round(hi, 2)], "n": len(inb), "confidence": round(conf, 3), "accuracy": round(acc, 3)})
    return round(ece, 3), out


def photo_eval(cases, systems):
    out = {}
    labels = sorted({c["label"] for c in cases["photos"]})
    for name, run in systems.items():
        rows = []
        for c in cases["photos"]:
            data = (PHOTOS / c["file"]).read_bytes()
            t0 = time.perf_counter()
            ranked = run(data)
            rows.append({"file": c["file"], "label": c["label"], "top": ranked[0][0], "conf": ranked[0][1],
                         "top2": [k for k, _ in ranked[:2]], "ms": (time.perf_counter() - t0) * 1000})
        sure = [r for r in rows if r["conf"] >= config.NOT_SURE_BELOW]
        unsure = [r for r in rows if r["conf"] < config.NOT_SURE_BELOW]
        per = {lab: f"{sum(r['top'] == lab for r in rows if r['label'] == lab)}/{sum(r['label'] == lab for r in rows)}" for lab in labels}
        confusion = Counter((r["label"], r["top"]) for r in rows if r["top"] != r["label"])
        ece, bins = calibration(rows)
        out[name] = {"accuracy": round(sum(r["top"] == r["label"] for r in rows) / len(rows), 3),
                     "ece": ece, "reliability": bins,
                     "confusion": {lab: dict(Counter(r["top"] for r in rows if r["label"] == lab)) for lab in labels},
                     "top2": round(sum(r["label"] in r["top2"] for r in rows) / len(rows), 3),
                     "said_not_sure": len(unsure),
                     "accuracy_when_sure": round(sum(r["top"] == r["label"] for r in sure) / len(sure), 3) if sure else None,
                     "accuracy_when_not_sure": round(sum(r["top"] == r["label"] for r in unsure) / len(unsure), 3) if unsure else None,
                     "per_problem": per, "common_mistakes": [f"{a} -> {b} ({n})" for (a, b), n in confusion.most_common(4)],
                     "median_ms": round(statistics.median(r["ms"] for r in rows))}
    return out


def text_eval(cases, systems):
    out = {}
    for name, run in systems.items():
        rows = []
        for c in cases["cases"]:
            ranked = run(c["text"])
            rows.append({"label": c["label"], "top": ranked[0][0], "conf": ranked[0][1], "text": c["text"]})
        per = defaultdict(lambda: [0, 0])
        for r in rows:
            per[r["label"]][0] += r["top"] == r["label"]
            per[r["label"]][1] += 1
        ece, bins = calibration(rows)
        out[name] = {"accuracy": round(sum(r["top"] == r["label"] for r in rows) / len(rows), 3),
                     "ece": ece, "reliability": bins,
                     "per_problem": {k: f"{a}/{b}" for k, (a, b) in per.items()},
                     "mistakes": [f"{r['text']!r}: expected {r['label']}, got {r['top']}" for r in rows if r["top"] != r["label"]]}
    return out


def safety_eval(cases):
    caught = [c for c in cases["positives"] if c["hazard"] in {h["id"] for h in rules.hazards(c["text"])}]
    any_warning = [c for c in cases["positives"] if rules.hazards(c["text"])]
    false_alarms = [c for c in cases["negatives"] if rules.hazards(c["text"])]
    return {"emergencies": len(cases["positives"]),
            "caught_right_warning": len(caught), "caught_any_warning": len(any_warning),
            "missed": [c["text"] for c in cases["positives"] if not rules.hazards(c["text"])],
            "near_misses": len(cases["negatives"]), "false_alarms": len(false_alarms),
            "false_alarm_examples": [c["text"] for c in false_alarms]}


def _ranked(d):
    return sorted(d["issue_and_alts"], key=lambda kv: -kv[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude", action="store_true")
    args = ap.parse_args()
    photo_cases = json.loads((HERE / "photo_cases.json").read_text())
    text_cases = json.loads((HERE / "text_cases.json").read_text())
    safety_cases = json.loads((HERE / "safety_cases.json").read_text())
    fetch_photos(photo_cases)

    def local_photo(style):
        return lambda data: sorted(models.photo_probs(models.load_image(data), style).items(), key=lambda kv: -kv[1])

    photo_systems = {"local, plain prompts": local_photo("names"), "local, written visual cues (used)": local_photo("cues")}
    text_systems = {"local text model (used)": lambda t: sorted(models.text_probs(t).items(), key=lambda kv: -kv[1])}

    if args.claude:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("--claude needs ANTHROPIC_API_KEY")

        def via_claude(image=None, text=""):
            r = dx.diagnose(image, text, engine="claude")
            if r["engine"] != "claude":
                raise SystemExit(f"Claude call failed: {r['errors']}")
            return [(r["issue"]["id"], r["issue"]["confidence"])] + [(a["id"], a["confidence"]) for a in r["alternatives"]]
        photo_systems[f"claude ({config.MODEL})"] = lambda data: via_claude(image=data)
        text_systems[f"claude ({config.MODEL})"] = lambda t: via_claude(text=t)

    print("Running photo eval...")
    photo = photo_eval(photo_cases, photo_systems)
    print("Running description eval...")
    text = text_eval(text_cases, text_systems)
    safety = safety_eval(safety_cases)
    heldout = safety_eval(json.loads((HERE / "safety_heldout.json").read_text()))

    print(f"\nPHOTOS ({len(photo_cases['photos'])} photos, 5 problem types; choosing among all 8)")
    print(f"{'system':38} {'right':>6} {'right in top 2':>15} {'said not sure':>14} {'right when sure':>16}")
    for k, s in photo.items():
        sure = "–" if s["accuracy_when_sure"] is None else f"{s['accuracy_when_sure']:.0%}"
        print(f"{k:38} {s['accuracy']:>6.0%} {s['top2']:>15.0%} {s['said_not_sure']:>14} {sure:>16}   ECE {s['ece']:.3f}")
    best = list(photo)[-1]
    print(f"  per problem ({best}): {photo[best]['per_problem']}")
    print(f"  most common mistakes: {photo[best]['common_mistakes']}")
    print(f"\nDESCRIPTIONS ({len(text_cases['cases'])} descriptions, 8 problem types)")
    for k, s in text.items():
        print(f"{k:38} {s['accuracy']:>6.0%}   ECE {s['ece']:.3f}   mistakes: {len(s['mistakes'])}")
        for m in s["mistakes"]:
            print(f"    - {m}")
    print("\nSAFETY RULES")
    for label, sf in (("first set (its misses were used to fix the rules)", safety),
                      ("held-out set (written before re-running; not tuned on)", heldout)):
        print(f"  {label}: caught {sf['caught_any_warning']}/{sf['emergencies']} emergencies, "
              f"{sf['false_alarms']}/{sf['near_misses']} false alarms")
        for m in sf["missed"]:
            print(f"    MISSED: {m!r}")
        for m in sf["false_alarm_examples"]:
            print(f"    FALSE ALARM: {m!r}")

    out_path = HERE / "results" / "latest.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps({"run_at": time.strftime("%Y-%m-%d"),
                                    "counts": {"photos": len(photo_cases["photos"]), "descriptions": len(text_cases["cases"])},
                                    "photos": photo, "descriptions": text, "safety": safety,
                                    "safety_heldout": heldout,
                                    "safety_heldout_first_run": {"caught": "19/20", "false_alarms": "0/20",
                                                                 "missed": ["water is running down the wall onto the power strip"],
                                                                 "note": "Recorded before that miss was fixed."}}, indent=2))
    print(f"\nSaved {out_path.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
