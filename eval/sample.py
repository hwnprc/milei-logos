"""Step 1: pick a random, reproducible sample of speech segments and create the blind fallacy labeling sheet.

Usage: python eval/sample.py --csv Milei_Hackathon_Transcriptions_2026.csv --n 50
"""
import argparse
import random

from common import FALLACY_LABELS_CSV, SAMPLE_CSV, load_logos, write_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="Milei_Hackathon_Transcriptions_2026.csv")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="overwrite an existing sample and labels")
    args = parser.parse_args()

    if SAMPLE_CSV.exists() and not args.force:
        raise SystemExit(f"{SAMPLE_CSV} already exists. Use --force to resample (this discards your labels).")

    logos = load_logos()
    segments = logos.load_speeches(args.csv)  # same filter as the app: SPEAKER_00, longer than 80 chars
    if len(segments) < args.n:
        raise SystemExit(f"Only {len(segments)} segments available, fewer than --n {args.n}.")

    picked = random.Random(args.seed).sample(segments, args.n)
    rows = [
        {"id": f"s{i:03d}", "date": s["date"], "title": s["title"], "type": s["type"], "text": s["text"]}
        for i, s in enumerate(picked, start=1)
    ]
    write_csv(SAMPLE_CSV, rows, ["id", "date", "title", "type", "text"])

    labels = [
        {"id": r["id"], "text": r["text"], "has_fallacy": "", "fallacy_types": "", "notes": ""}
        for r in rows
    ]
    write_csv(FALLACY_LABELS_CSV, labels, ["id", "text", "has_fallacy", "fallacy_types", "notes"])

    print(f"Sampled {args.n} of {len(segments)} segments -> {SAMPLE_CSV}")
    print(f"Label these BEFORE running Logos -> {FALLACY_LABELS_CSV}")
    print("  has_fallacy: yes / no    fallacy_types: e.g. false dichotomy; cherry-picking")


if __name__ == "__main__":
    main()
