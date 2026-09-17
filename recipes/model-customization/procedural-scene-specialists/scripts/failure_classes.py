"""Bucket a run's failures by cause, so contract rounds are judged by what changed — not by the pass rate alone.

Across three rounds of contract edits on one segment, every rule added eliminated the class it targeted and the pass rate
never moved, because a new class replaced it each time. Reading only the rate would have said "prompt tuning does not
help". Reading the table said "you are trading one error for another; stop when a class survives two rounds".

  python scripts/failure_classes.py data/ocean_probe                    # one run
  python scripts/failure_classes.py data/ocean_v1 data/ocean_v2 ...     # compare rounds side by side
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

CLASSES = [
    (r"ERROR: 0:\d+: '\w+' : (?:vector field|field selection)", "GLSL swizzle / field selection"),
    (r"'\w+' : redefinition", "GLSL redefinition"),
    (r"'\w+' : undeclared identifier", "GLSL undeclared identifier"),
    (r"ERROR: 0:", "GLSL other"),
    (r"does not evolve", "no animation"),
    (r"Class constructor .* cannot be invoked", "JS: missing `new`"),
    (r"Cannot read properties of undefined", "JS: undefined member"),
    (r"console/page errors", "JS runtime, other"),
    (r"degenerate repetition", "degenerate output"),
]


def classify(run: Path) -> tuple[int, int, int, collections.Counter]:
    rows = {}
    for line in (run / "log.jsonl").read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        rows[r.get("id")] = r
    kinds = collections.Counter()
    passes = first = 0
    for r in rows.values():
        if r.get("pass"):
            passes += 1
            first += not r.get("revised")
            continue
        note = " ".join(str(n) for n in (r.get("notes") or [])) + " " + str(r.get("error", ""))
        for pat, label in CLASSES:
            if re.search(pat, note):
                kinds[label] += 1
                break
        else:
            kinds["checks failed (ran and rendered)" if r.get("gate", 0) >= 0.8 else "other"] += 1
    return passes, len(rows), first, kinds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    args = ap.parse_args()
    data = {}
    for r in args.runs:
        p = Path(r)
        if not (p / "log.jsonl").exists():
            print(f"skip {r}: no log.jsonl")
            continue
        data[p.name] = classify(p)
    if not data:
        raise SystemExit("no runs to report")

    names = list(data)
    w = max(len(n) for n in names + ["checks failed (ran and rendered)"]) + 2
    print(f"{'':{w}}" + "".join(f"{n[:14]:>16s}" for n in names))
    print(f"{'PASS':{w}}" + "".join(f"{data[n][0]:>10d}/{data[n][1]:<5d}" for n in names))
    print(f"{'  first attempt':{w}}" + "".join(f"{data[n][2]:>16d}" for n in names))
    print("-" * (w + 16 * len(names)))
    for label in sorted({k for d in data.values() for k in d[3]}):
        print(f"{label:{w}}" + "".join(f"{data[n][3].get(label, 0):>16d}" for n in names))
    print("\nFix one class per round, re-run the same briefs, and stop when a class survives two rounds — at that point "
          "the remaining errors are consistency slips that fine-tuning fixes, not wording.")


if __name__ == "__main__":
    main()
