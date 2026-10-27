"""Step 3: compare Logos against your labels and write eval/report.md.

Usage: python eval/score.py
Scores whatever is labeled so far, so you can run it part-way through.
"""
import json
import re
import statistics
from collections import Counter

from common import (CLAIM_LABELS_CSV, EVAL_DIR, FALLACY_LABELS_CSV, RESULTS_DIR, SAMPLE_CSV, VERDICTS,
                    read_csv, write_csv)
from run_logos import parse_verdict

PREDICTIONS_CSV = RESULTS_DIR / "fallacy_predictions.csv"
REPORT_MD = EVAL_DIR / "report.md"

# Canonical fallacy name -> spellings that count as it (lowercase).
FALLACIES = {
    "false dichotomy": ["false dichotomy", "false dilemma", "black-and-white", "either/or"],
    "cherry-picking": ["cherry-picking", "cherry picking", "selective evidence", "selectively true"],
    "appeal to fear": ["appeal to fear", "fear-mongering", "scare tactic"],
    "appeal to emotion": ["appeal to emotion", "emotional appeal", "appeal to pity"],
    "non sequitur": ["non sequitur", "non-sequitur", "does not follow"],
    "straw man": ["straw man", "strawman"],
    "ad hominem": ["ad hominem", "personal attack"],
    "slippery slope": ["slippery slope"],
    "hasty generalization": ["hasty generalization", "overgeneralization", "sweeping generalization"],
    "false cause": ["false cause", "post hoc", "correlation", "causal fallacy", "questionable cause"],
    "appeal to authority": ["appeal to authority"],
    "red herring": ["red herring"],
    "begging the question": ["begging the question", "circular reasoning", "circular argument"],
    "whataboutism": ["whataboutism", "tu quoque"],
    "bandwagon": ["bandwagon", "appeal to popularity"],
    "loaded language": ["loaded language", "loaded term"],
}
NO_FALLACY = re.compile(r"\bno (clear |obvious |explicit |major )?(logical )?fallac|\bnone (were )?(detected|identified|found)|^\W*none\b",
                        re.I | re.M)


def fallacy_section(report: str) -> str:
    """Text under the aggregator's 'Fallacies Detected' heading, up to the next numbered or markdown heading."""
    lines = report.splitlines()
    start = next((i for i, l in enumerate(lines) if re.search(r"fallac", l, re.I) and re.match(r"\s*(#|\d+\.|\*\*)", l)), None)
    if start is None:
        return ""
    body = [re.sub(r"^.*?fallacies detected\W*", "", lines[start], flags=re.I)]
    for line in lines[start + 1:]:
        if re.match(r"\s*(#{1,6}\s|\d+\.\s*\*\*|\*\*\d+\.)", line):
            break
        body.append(line)
    return "\n".join(body).strip()


def canonical_types(text: str) -> set:
    low = text.lower()
    return {name for name, spellings in FALLACIES.items() if any(s in low for s in spellings)}


def parse_fallacies(report: str):
    section = fallacy_section(report)
    if not section or NO_FALLACY.search(section):
        return False, set(), section
    return True, canonical_types(section) or {"other"}, section


def yes(value: str):
    v = value.strip().lower()
    return True if v in ("yes", "y", "true", "1") else False if v in ("no", "n", "false", "0") else None


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a (nothing labeled yet)"


def main():
    sample = read_csv(SAMPLE_CSV)
    results = {}
    for seg in sample:
        path = RESULTS_DIR / f"{seg['id']}.json"
        if path.exists():
            results[seg["id"]] = json.loads(path.read_text(encoding="utf-8"))

    # Pipeline reliability and speed: no labels needed.
    statuses = Counter(r["status"] for r in results.values())
    ok_times = [r["seconds_total"] for r in results.values() if r["status"] == "ok"]
    claim_counts = [len(r["claims"]) for r in results.values() if r["status"] == "ok"]

    # Fallacy predictions, keeping any corrections you typed into the predictions sheet.
    corrections = {}
    if PREDICTIONS_CSV.exists():
        corrections = {r["id"]: r["corrected_has_fallacy"] for r in read_csv(PREDICTIONS_CSV)}
    pred_rows, predicted = [], {}
    for sid, r in results.items():
        if r["status"] == "no_claims":
            has, types, section = False, set(), "(no claims extracted: treated as no fallacy)"
        elif r["status"] != "ok":
            continue
        else:
            has, types, section = parse_fallacies(r["final_report"])
        corrected = corrections.get(sid, "")
        if yes(corrected) is not None:
            has = yes(corrected)
        predicted[sid] = (has, types)
        pred_rows.append({"id": sid, "parsed_has_fallacy": "yes" if has else "no",
                          "parsed_types": "; ".join(sorted(types)), "corrected_has_fallacy": corrected,
                          "section_text": section})
    write_csv(PREDICTIONS_CSV, pred_rows,
              ["id", "parsed_has_fallacy", "parsed_types", "corrected_has_fallacy", "section_text"])

    # Fallacy detection vs. your segment labels.
    tp = fp = fn = tn = type_hits = 0
    for row in read_csv(FALLACY_LABELS_CSV) if FALLACY_LABELS_CSV.exists() else []:
        truth = yes(row["has_fallacy"])
        if truth is None or row["id"] not in predicted:
            continue
        has, types = predicted[row["id"]]
        if truth and has:
            tp += 1
            type_hits += bool(types & canonical_types(row["fallacy_types"]))
        elif truth:
            fn += 1
        elif has:
            fp += 1
        else:
            tn += 1

    # Claim extraction and fact-check agreement vs. your claim labels.
    faithful = faithful_n = agree = agree_n = 0
    confusion = Counter()
    for row in read_csv(CLAIM_LABELS_CSV) if CLAIM_LABELS_CSV.exists() else []:
        sid, idx = row["claim_id"].rsplit("-c", 1)
        r = results.get(sid)
        if not r or r["status"] != "ok":
            continue
        f = yes(row["claim_is_faithful"])
        if f is not None:
            faithful_n += 1
            faithful += f
        human = row["human_verdict"].strip().upper()
        if f is False or human not in VERDICTS:
            continue
        logos_v = parse_verdict(r["worker_analyses"][int(idx) - 1])
        confusion[(human, logos_v)] += 1
        agree_n += 1
        agree += human == logos_v

    lines = [
        "# Logos evaluation report", "",
        f"Segments run: {len(results)} of {len(sample)}", "",
        "## Reliability and speed (no labels needed)", "",
        "| Metric | Value |", "|---|---|",
        f"| Completed the full pipeline | {pct(statuses['ok'], len(results))} |",
        f"| No claims found (pure rhetoric) | {statuses['no_claims']} |",
        f"| Orchestrator returned broken JSON | {statuses['orchestrator_json_error']} |",
        f"| API errors | {statuses['llm_error']} |",
        f"| Median time per segment | {statistics.median(ok_times):.1f}s |" if ok_times else "| Median time per segment | n/a |",
        f"| Claims extracted per segment (avg) | {statistics.mean(claim_counts):.1f} |" if claim_counts else "| Claims extracted per segment (avg) | n/a |",
        "", "## Fallacy detection (vs. your segment labels)", "",
        "| Metric | Value |", "|---|---|",
        f"| Catch rate: real fallacies Logos flagged (recall) | {pct(tp, tp + fn)} |",
        f"| Precision: Logos flags that were real fallacies | {pct(tp, tp + fp)} |",
        f"| False alarms on clean segments | {pct(fp, fp + tn)} |",
        f"| Right fallacy type, when both said yes | {pct(type_hits, tp)} |",
        "", "## Claims (vs. your claim labels)", "",
        "| Metric | Value |", "|---|---|",
        f"| Extracted claims faithful to the speech | {pct(faithful, faithful_n)} |",
        f"| Fact-check verdict matches yours | {pct(agree, agree_n)} |",
        "", "Verdict confusion (rows = you, columns = Logos):", "",
        "| you \\ Logos | " + " | ".join(VERDICTS + ["UNPARSED"]) + " |",
        "|---" * (len(VERDICTS) + 2) + "|",
    ]
    for h in VERDICTS:
        lines.append(f"| {h} | " + " | ".join(str(confusion[(h, l)]) for l in VERDICTS + ["UNPARSED"]) + " |")
    lines += ["", f"Fallacy parsing is automatic. Check `{PREDICTIONS_CSV.relative_to(EVAL_DIR.parent)}` and "
              "type yes/no in `corrected_has_fallacy` wherever the parser got it wrong, then re-run."]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
