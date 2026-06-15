"""Render an eval run (results/latest.jsonl) to a markdown summary.

    python -m evals.report                      # read results/latest.jsonl
    python -m evals.report path/to/run.jsonl

Prints per-category pass rate with a 95% Wilson interval, pass^k for E1 (the
reliability-critical core), and false-log rate for E4. Appends a one-line
summary row to results/HISTORY.md.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


def _wilson(passes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = passes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(rows: list[dict]) -> str:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r.get("category") or "?"].append(r)

    lines = ["| Category | Cases×trials | Pass rate | 95% CI | Notes |",
             "|----------|--------------|-----------|--------|-------|"]
    for cat in sorted(by_cat):
        crows = by_cat[cat]
        n = len(crows)
        passes = sum(1 for r in crows if r["passed"])
        lo, hi = _wilson(passes, n)
        note = ""
        if cat == "E1":
            # pass^k: fraction of cases where ALL trials passed
            by_case: dict[str, list[bool]] = defaultdict(list)
            for r in crows:
                by_case[r["id"]].append(r["passed"])
            clean = sum(1 for v in by_case.values() if all(v))
            note = f"pass^k: {clean}/{len(by_case)} cases all-trials-clean"
        if cat == "E4":
            false_logs = n - passes
            note = f"false-log rate: {false_logs}/{n} = {false_logs / n:.0%}" if n else ""
        lines.append(
            f"| {cat} | {n} | {passes / n:.0%} | [{lo:.0%}, {hi:.0%}] | {note} |"
        )

    total = len(rows)
    tot_pass = sum(1 for r in rows if r["passed"])
    lines.append(f"\n**Overall: {tot_pass}/{total} = {tot_pass / total:.0%}**" if total else "\n_No rows._")

    fails = [r for r in rows if not r["passed"]]
    if fails:
        lines.append("\n### Failing (case, trial) rows\n")
        for r in fails[:20]:
            lines.append(f"- `{r['id']}` t{r['trial']}: {r['reason']}")
    return "\n".join(lines)


def append_history(rows: list[dict]) -> None:
    if not rows:
        return
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        by_cat[r.get("category") or "?"].append(r["passed"])
    cats = " ".join(f"{c}:{sum(v)}/{len(v)}" for c, v in sorted(by_cat.items()))
    model = rows[0].get("model_id", "?")
    sha = rows[0].get("git_sha", "") or "—"
    hist = RESULTS_DIR / "HISTORY.md"
    line = f"| {date.today().isoformat()} | {sha} | {model} | {cats} |\n"
    if not hist.exists():
        hist.write_text("# Eval run history\n\n| Date | Git SHA | Model | Per-category passes |\n|------|---------|-------|---------------------|\n")
    with hist.open("a") as fh:
        fh.write(line)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else RESULTS_DIR / "latest.jsonl"
    if not path.exists():
        print(f"No results at {path}. Run `pytest evals/ -m capability` first.")
        return
    rows = load(path)
    print(summarize(rows))
    append_history(rows)
    print(f"\nAppended summary row to {RESULTS_DIR / 'HISTORY.md'}")


if __name__ == "__main__":
    main()
