# Logos eval kit

Measures how reliable Logos is by comparing it with your own labels on a random sample of 50 speech segments. It uses the exact prompts and GPT-4o calls in `milei-logos.py`; nothing in the app changes.

What you get in `eval/report.md`:

| Number | What it tells you | Needs labels? |
|---|---|---|
| Completed the full pipeline, median time per segment | Reliability and speed | No |
| Fallacy catch rate (recall), precision, false alarms | Does it find real fallacies without crying wolf? | Fallacy sheet |
| Claims faithful to the speech | Does the orchestrator extract real claims? | Claim sheet |
| Fact-check verdict matches yours | How often the worker's TRUE/FALSE/MISLEADING/UNVERIFIABLE matches a human | Claim sheet |

## Setup

```bash
pip install openai python-dotenv   # streamlit is optional for the eval
```

Put `Milei_Hackathon_Transcriptions_2026.csv` in the repo root and your key in `.env` (`OPENAI_API=...`), as for the app.

## Steps

**1. Sample 50 segments (free, no API calls)**

```bash
python eval/sample.py --n 50
```

**2. Label fallacies BEFORE you see any Logos output.** Open `eval/labels/fallacy_labels.csv` in Google Sheets or Excel. For each segment fill `has_fallacy` (yes/no) and `fallacy_types` (e.g. `false dichotomy; cherry-picking`). Labeling first keeps the AI from anchoring you. About 1–1.5 hours.

**3. Run Logos on the sample (about 50 × 8 GPT-4o calls; roughly a few dollars)**

```bash
python eval/run_logos.py
```

Results are saved per segment in `eval/results/`, so you can stop and re-run; finished segments are skipped. This also creates `eval/labels/claim_labels.csv`, one row per claim Logos extracted, **without** Logos' verdict.

**4. Label the claims.** For each row fill `claim_is_faithful` (yes/no: did Milei actually say or imply this?) and `human_verdict` (TRUE/FALSE/MISLEADING/UNVERIFIABLE). Use real sources (INDEC, BCRA, Chequeado). About 1.5–2 hours for ~100 claims. Asking the La Nación journalist to check 10–20 of your labels makes the numbers much stronger.

**5. Score**

```bash
python eval/score.py
```

You can run it any time; it scores whatever is labeled. Fallacies are read automatically from the aggregator's "Fallacies Detected" section. Skim `eval/results/fallacy_predictions.csv` and type yes/no in `corrected_has_fallacy` where the parser misread the report, then re-run.

## Privacy

`eval/data/`, `eval/labels/` and `eval/results/` contain speech text from the La Nación dataset and are git-ignored. Only `eval/report.md` (numbers only) is meant to be committed. Remove those lines from `.gitignore` if you have permission to publish the data.

## Then

Write up 3–5 cases where Logos was wrong and why. That plus the report is your public eval write-up.
