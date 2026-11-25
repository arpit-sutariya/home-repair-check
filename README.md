# Home Repair Check

**Something wrong at home? Snap a photo, describe it, and get a straight answer in a minute:**
1. What it probably is
2. How urgent it is
3. Who to call
4. What it should cost
5. Whether a contractor's quote looks fair
6. Who near you can fix it: real local pros with phone numbers, addresses and directions

It also writes a message you can send to contractors.

<p align="center">
  <img src="docs/screenshots/demo.gif" width="656" alt="Demo: a ceiling-stain photo near USC, Los Angeles is checked (water stain, 81%, fix within a few weeks) with a How it decided panel; a sparking outlet triggers a safety warning and lists real electricians near USC with phone numbers, hours, Call and Directions buttons; a quote is checked against sourced price ranges; the eval report shows accuracy and calibration">
</p>

## Why

Homeowners face the same three worries with every repair: *Is this serious? Who do I call? Am I being overcharged?* Contractors know far more than the customer, and that gap is where people overpay or wait too long. This app closes the gap before the first phone call.

## What you get

| | |
|---|---|
| **Safety first** | Gas smells, sparking outlets, water near electricity, a sagging ceiling, carbon monoxide or sewage get a clear "do this now" warning before anything else. |
| **What it probably is** | One of eight common problems, with how sure it is. When it's unsure, it shows the runner-up and the one question that tells them apart. |
| **How urgent** | From "Can wait" to "Act now", with the reason ("you mentioned it's getting bigger"). |
| **Who to call, and whether it's DIY** | Plus what to do right now: what to check, what to turn off. |
| **What it usually costs** | Typical US price ranges, each linked to the public cost guide it came from. |
| **Quote check** | Enter a contractor's total to see whether it's unusually low, typical, or above the usual range, and what to ask. |
| **Pros near you** | Type a city, neighborhood or ZIP (e.g. "USC, Los Angeles") or tap "Use my location". You get real businesses for the trades this problem needs (plumber, roofer, electrician…), closest first, with Call, Website and Directions buttons. Listings come from Google Places if a key is set, otherwise from free OpenStreetMap data. They are never generated. Every trade also gets Google Maps and Yelp search links. |
| **Message to contractors** | Ready to copy or email, including the questions worth asking for that problem. |
| **How it decided** | Every problem's score from the photo and the description separately, the location nudge, which of your words triggered a safety rule, and the engine, latency and tokens. |
| **Live eval report** | `/evals` shows the measurements below as charts: the prompt ablation, a confusion matrix, a calibration (reliability) diagram and the safety results. |


## How it decides

The AI only answers one question: *which problem is this?* Everything that has to be right every time is plain code:

| Part | Decided by |
|---|---|
| Safety warnings | Rules on the customer's own words, checked before any AI runs |
| What the problem is | Local AI models (free, no API key), or Claude if a key is set |
| Urgency, prices, quote verdict, message | Code and a knowledge file (`repaircheck/knowledge.json`) |
| Which trades to call, and who's nearby | The knowledge file maps each problem to trades; real listings come from Google Places or OpenStreetMap (`repaircheck/pros.py`) |

So the AI can't invent a price, and can't talk a gas leak down to "not urgent". With Claude switched on, it can *add* a safety warning it sees in the photo, but never remove one.

## Results

I measured three things. All test data is described below, and every number can be rerun with `python -m eval.run_eval`.

**1. Reading photos.** 75 real photos of five problems (15 each), choosing among all eight problem types:

| How the photo model is prompted | Right | Right in top 2 |
|---|---|---|
| Plain names ("a photo of mold growth") | 59% | 83% |
| **Written visual cues from the knowledge file (used)** | **81%** | **92%** |

Writing down what each problem *looks like* (e.g. "a brown or yellow water stain on a ceiling") added 22 points without changing the model. It also catches its own uncertainty: on the photos where it was sure, it was right 86% of the time.
- **Strongest:** cracks and stair-step cracks (15/15 each).
- **Weakest:** mold (8/15). Mold is most often mistaken for a water stain, which is a reasonable confusion, since mold often grows on water stains.

**Are the confidence numbers honest?** Expected calibration error (ECE) is **0.097 for photos and 0.048 for descriptions** (0 = perfectly honest). The photo model leans cautious: on photos where it said about 71% sure, it was right 89% of the time. Its few low-confidence answers (about 33%) were all wrong, which is exactly where it says "not sure". The `/evals` page plots this.

**2. Reading descriptions.** 48 homeowner-style descriptions ("theres a yellowish ring on my ceiling right below the upstairs tub"), 8 problem types: **92% right.** The 4 misses are genuinely ambiguous, like "a damp spot that keeps coming back".

**3. Safety warnings.** This is the part that has to work:
- **First test (30 emergencies + 30 near-misses):** it caught only **23 of 30 emergencies** and gave 2 false alarms ("spark plug", "burnt toast set off the smoke alarm"). I broadened the rules using those misses.
- **Fresh held-out set:** to check the fix honestly, I then wrote 20 new emergencies and 20 new near-misses *before* re-running. Result: **19 of 20 caught, 0 false alarms.** The one miss ("water running down the wall onto the power strip") is now fixed too.
- **Every case from both sets is now a permanent test**, so a future change can't quietly break one.

**Not measured yet:** Claude's accuracy. That needs an API key; run `python -m eval.run_eval --claude` to add it to the comparison.

## Run it

Requires Python 3.10+ (tested on 3.13). The first start downloads the local models, about 700 MB, once.

```bash
git clone https://github.com/arpit-sutariya/home-repair-check.git
cd home-repair-check
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000      # open http://localhost:8000  (eval report: /evals)
```

- While the models load, the page shows "Starting the local AI models"; you can fill in the form meanwhile.
- No photo handy? Click one of the four sample photos under the upload box.
- Optional: put `ANTHROPIC_API_KEY` in a `.env` file (see `.env.example`) to use Claude instead of the local models.
- Optional: put `GOOGLE_PLACES_API_KEY` in `.env` for much better local contractor listings (ratings, reviews, "open now"). Without it the app uses free OpenStreetMap data, which is good for some trades (electricians and plumbers near USC, for example) and empty for others (roofers there). Every trade always gets Google Maps and Yelp search links, so there's never a dead end.

**Tests and evals**

```bash
pytest -q                     # 138 tests, no API key or model download needed
python -m eval.run_eval       # downloads the 75 test photos (~40 MB) the first time, then updates /evals
python -m eval.run_eval --claude   # also scores Claude (needs ANTHROPIC_API_KEY)
```

**Docker**

```bash
docker build -t home-repair-check .          # bakes the models into the image
docker run -p 8000:8000 home-repair-check    # add  -e ANTHROPIC_API_KEY=...  for Claude
```

## Inspiration and credits

- **Inspired by [MaestrIA](https://claude.com/resources/articles/meet-the-winners-of-built-with-opus-4-7-claude-code-hackathon)** from Anthropic's Built with Opus 4.7 hackathon, which diagnoses home repairs from photos for homeowners in Chile. This is an independent build with its own design and code.
- **Test photos:** [senthilsk/crack_detection_dataset](https://huggingface.co/datasets/senthilsk/crack_detection_dataset) (from Roboflow's *detr_crack_dataset*), CC BY 4.0. The eval downloads them; they aren't stored in this repo. The photo in the screenshot above is from this dataset.
- **Price ranges:** the public cost guides linked next to each range in the app and in `knowledge.json` (This Old House, Angi, HomeAdvisor, Fixr, Inch Calculator and others), checked November 2026.

## Limitations

- It covers eight common problems. Anything else gets its best guess and a "not sure" when confidence is low.
- **Prices are national ranges**, a sanity check rather than a quote. Local prices can be quite different.
- The safety rules catch common wording. No list of rules catches everything, so the app always says to call a professional or 911 when something feels unsafe.
- **The test sets are small**, and I wrote the descriptions and safety cases myself.
- **Local listings depend on the source.** OpenStreetMap is free but patchy, and its public servers are sometimes overloaded (the app then falls back to OpenStreetMap's search service and skips the busy server for 5 minutes). Listings aren't vetted; the app says to check licensing, insurance and reviews.
- **Memory:** the photo model needs about 900 MB of RAM, so a free hosting plan (512 MB) isn't enough. See `render.yaml`.

More detail: [HOW_IT_WORKS.md](HOW_IT_WORKS.md).

## License

MIT
