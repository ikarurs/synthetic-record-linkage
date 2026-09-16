"""Rebuild the complete offline demonstration: python run.py."""
import argparse
import json
from pathlib import Path

from linkage import (CANDIDATE_FIELDS, DECISION_FIELDS, ISSUE_FIELDS, RECORD_FIELDS,
                     candidates, evaluate, extract, find_matches, read_csv, threshold_sweep, write_csv)
from synthetic import make_dataset
from visualise import save_figures


def run(data, output):
    output.mkdir(parents=True, exist_ok=True)
    records, issues = extract(data / "pages")
    pairs = candidates(records)
    decisions = find_matches(records, pairs)
    # Truth enters only AFTER extraction and matching have finished.
    truth = read_csv(data / "truth.csv")
    if {r["record_id"] for r in records if int(r["year"]) == 1920} != {r["left_id"] for r in truth}:
        raise ValueError("Truth and baseline extraction do not cover the same identities")
    right_ids = {r["record_id"] for r in records if int(r["year"]) == 1930}
    if {r["right_id"] for r in truth if r["right_id"]} - right_ids:
        raise ValueError("Truth refers to missing later records")
    metrics = {split: evaluate(decisions, pairs, [r for r in truth if r["split"] == split])
               for split in ("development", "heldout")}
    metrics["all"] = evaluate(decisions, pairs, truth)
    metrics["extraction"] = dict(parsed=len(records), rejected=len(issues))
    sweep = threshold_sweep(records, pairs, [r for r in truth if r["split"] == "development"])
    for name, rows, fields in (("records", records, RECORD_FIELDS), ("extraction_issues", issues, ISSUE_FIELDS),
                               ("candidates", pairs, CANDIDATE_FIELDS), ("matches", decisions, DECISION_FIELDS),
                               ("thresholds", sweep, list(sweep[0]))):
        write_csv(output / f"{name}.csv", rows, fields)
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    save_figures(output, pairs, truth, decisions, sweep)
    print(json.dumps(metrics, indent=2, allow_nan=False))
    return metrics


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=root / "data")
    parser.add_argument("--output", type=Path, default=root / "outputs")
    parser.add_argument("--regenerate", action="store_true", help="Recreate only the synthetic demo input files")
    args = parser.parse_args()
    if args.regenerate:
        make_dataset(args.data)
    run(args.data, args.output)
