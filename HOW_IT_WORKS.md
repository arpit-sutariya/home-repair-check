# How it works

## One check, start to finish

```
photo + description + location
  ➙ safety rules on the description                  (rules.hazards: code, runs first)
  ➙ which problem is it?                             (local models, or Claude)
      photo: CLIP compares the image with written visual cues for each problem
      words: a small text model compares the description with each problem's symptoms
      both:  average the two, then nudge by location ("outlet or switch" ➙ outlet problems)
  ➙ urgency, price tiers, quote verdict, message     (rules.py + knowledge.json: code)
```

## Why the AI only picks the problem

Every output that can hurt someone if it's wrong is decided by code:
- **A safety warning.** Missing one could get someone hurt.
- **A price.** An invented price misleads someone about to sign a quote.
- **Urgency.** It has to be explainable ("you mentioned it's getting bigger").

The AI does the part code can't: looking at a photo or reading "theres a yellowish ring on my ceiling" and mapping it to a known problem.

That split is what makes it testable. The safety rules are checked against 100 written cases. The photo and description models each get their own accuracy number. A failure in one part can't silently change another.

## The knowledge file

`repaircheck/knowledge.json` holds everything the app knows about each of the eight problems:
- **What it looks like:** the visual cues for the photo model.
- **How people describe it:** the symptoms, for the text model.
- **Urgency:** a starting level and the words that raise it ("spreading", "doors stick").
- **Who to call, what's DIY, and what to do right now.**
- **Price tiers:** some apply only when the description mentions something specific. For example, "soaked" or "whole ceiling" adds a water-damage restoration tier. Each tier carries its source.
- **Questions to ask a contractor**, and the one question that tells this problem apart from its look-alike.

**Why it matters:** in the photo eval, using the written visual cues instead of plain problem names raised accuracy from 59% to 81% with no other change. The same file also fixed description wording during development ("doors started sticking" now raises the urgency).

## Not sure is an answer

If the top problem is below 45% likely (a threshold set before testing), the app says it's not sure. It then shows the runner-up and asks the question that tells the two apart. On photos where the model was sure, it was right 86% of the time. Saying "not sure" is better than a confident wrong answer that sends someone to the wrong tradesperson.

## The quote check

A quote is compared with the price tiers that apply:

| Quote | Verdict |
|---|---|
| Below 60% of the lowest tier | **Unusually low.** Ask what's included; low quotes can skip the cause or add charges later. |
| Up to the combined high end | **Typical** |
| Up to 1.5× the high end | **Above the usual range.** Ask for an itemized quote and get more bids. |
| Beyond that | **Far above.** Get more quotes. For structural problems only, it also suggests an independent engineer. |

## Claude (optional)

With an API key, Claude gets the photo (as an image) and the description. It has to answer through a tool that only accepts one of the eight problem ids, or "unknown". An invented id is ignored and the app says it's not sure.

Claude can also flag a safety concern it sees in the photo. That warning is *added* to the rule-based ones, never used to remove one. If the API fails, the app falls back to the local models, so the customer still gets an answer.

## Evals

`python -m eval.run_eval` (add `--claude` to include Claude):
- **Photos:** 75 photos from a CC BY 4.0 defect dataset, 15 each of crack, stair-step crack, mold, water seepage and peeling paint. Compares plain prompts with written visual cues.
- **Descriptions:** 48 casual homeowner descriptions across all 8 problems, written before the first run.
- **Safety:** a first set (30 emergencies + 30 near-misses) and a held-out set (20 + 20) written after the first set exposed gaps, before re-running.
  - First set: caught 23/30, with 2 false alarms.
  - Held-out set: caught 19/20, with 0 false alarms.

## Questions to be ready for

- **"Why not let the model do everything?"** Because the outputs with consequences (safety, money) need to be right and explainable every time. Code gives you that; a model doesn't.
- **"How did you know the safety rules worked?"** I didn't at first: the first test caught 23 of 30. The answer was to fix them and then measure on a fresh set I hadn't tuned on, rather than report the re-run on the set I fixed against.
- **"What would you improve next?"**
  1. Run the Claude comparison.
  2. Add regional price adjustments from a real data source.
  3. Collect real customer photos with permission to grow the test set.
  4. Add a second safety layer that matches by meaning, to catch wording the rules miss.
