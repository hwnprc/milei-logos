"""Step 2: run the full Logos pipeline on every sampled segment, save each result, and create the blind claim labeling sheet.

Usage: python eval/run_logos.py
Safe to re-run: segments that already have a result are skipped.
"""
import argparse
import asyncio
import json
import re
import time

from common import CLAIM_LABELS_CSV, RESULTS_DIR, SAMPLE_CSV, read_csv, write_csv, load_logos

LLM_ERROR = "Error calling LLM:"


async def analyze(logos, segment: str) -> dict:
    """Mirrors run_logos_workflow() in milei-logos.py, without the Streamlit UI."""
    out = {"status": "ok", "claims": [], "worker_analyses": [], "formalizer_analyses": [], "final_report": ""}
    timings = {}

    t = time.perf_counter()
    raw = await logos.llm_call_async(logos.get_orchestrator_prompt(segment), model="gpt-4o")
    timings["orchestrator"] = time.perf_counter() - t
    out["orchestrator_raw"] = raw
    if raw.startswith(LLM_ERROR):
        out["status"] = "llm_error"
        return out | {"timings": timings}
    try:
        claims = json.loads(raw.replace("```json", "").replace("```", "").strip())
    except json.JSONDecodeError:
        out["status"] = "orchestrator_json_error"
        return out | {"timings": timings}
    if not claims:
        out["status"] = "no_claims"
        return out | {"timings": timings}
    out["claims"] = claims

    t = time.perf_counter()
    workers = await logos.run_llm_parallel([
        {"user_prompt": logos.get_worker_prompt(segment, c["claim"], c["domain"], c["description"]), "model": "gpt-4o"}
        for c in claims
    ])
    timings["workers"] = time.perf_counter() - t

    t = time.perf_counter()
    formalizers = await logos.run_llm_parallel([
        {"user_prompt": logos.get_formalizer_prompt(c["claim"], w), "model": "gpt-4o"}
        for c, w in zip(claims, workers)
    ])
    timings["formalizers"] = time.perf_counter() - t

    t = time.perf_counter()
    report = await logos.llm_call_async(
        logos.get_aggregator_prompt(segment, claims, workers, formalizers), model="gpt-4o"
    )
    timings["aggregator"] = time.perf_counter() - t

    out.update(worker_analyses=workers, formalizer_analyses=formalizers, final_report=report)
    if any(x.startswith(LLM_ERROR) for x in [*workers, *formalizers, report]):
        out["status"] = "llm_error"
    return out | {"timings": timings}


def parse_verdict(worker_analysis: str) -> str:
    m = re.search(r"\*\*Verdict:\*\*\s*\**\s*(TRUE|FALSE|MISLEADING|UNVERIFIABLE)", worker_analysis, re.I)
    return m.group(1).upper() if m else "UNPARSED"


def build_claim_sheet(sample):
    """One row per extracted claim. Logos' verdict is left out so labeling stays blind."""
    rows = []
    for seg in sample:
        path = RESULTS_DIR / f"{seg['id']}.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        for i, c in enumerate(result["claims"], start=1):
            rows.append({
                "claim_id": f"{seg['id']}-c{i}",
                "segment_text": seg["text"],
                "claim": c.get("claim", ""),
                "claim_is_faithful": "",
                "human_verdict": "",
                "notes": "",
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite an existing claim labeling sheet")
    args = parser.parse_args()

    logos = load_logos()
    sample = read_csv(SAMPLE_CSV)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for n, seg in enumerate(sample, start=1):
        path = RESULTS_DIR / f"{seg['id']}.json"
        if path.exists():
            continue
        t = time.perf_counter()
        result = asyncio.run(analyze(logos, seg["text"]))
        result["seconds_total"] = round(time.perf_counter() - t, 2)
        result["id"] = seg["id"]
        result["segment"] = seg["text"]
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{n}/{len(sample)}] {seg['id']}: {result['status']}, {len(result['claims'])} claims, {result['seconds_total']}s")

    if CLAIM_LABELS_CSV.exists() and not args.force:
        print(f"{CLAIM_LABELS_CSV} already exists, left unchanged (use --force to rebuild it).")
        return
    rows = build_claim_sheet(sample)
    write_csv(CLAIM_LABELS_CSV, rows,
              ["claim_id", "segment_text", "claim", "claim_is_faithful", "human_verdict", "notes"])
    print(f"Wrote {len(rows)} claims to label -> {CLAIM_LABELS_CSV}")
    print("  claim_is_faithful: yes / no   human_verdict: TRUE / FALSE / MISLEADING / UNVERIFIABLE")


if __name__ == "__main__":
    main()
