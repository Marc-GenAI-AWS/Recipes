"""Calibrate a segment check against the host's own hand-built layer, before that check gates anything.

A check is a specification. If the reference layer only just clears its threshold, the check is a coin toss and will
reject good work; if it passes trivially, it will accept an empty layer. Both happened here:

  water_presence   reference scores 43-45 against a threshold of 8   comfortable
  herd_presence    reference scores 1.13-3.8 against a threshold of 1.0   knife-edge, months of false failures
  (a sky check that did not exist at all let domes that never wrote a pixel pass every gate)

Run this whenever you add or change a check, and paste the numbers into the check's docstring.

  python scripts/calibrate_check.py highpark layers/herd.js herd_presence
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import SCENES  # noqa: E402
from pipeline.harness.checks import CHECKS  # noqa: E402
from pipeline.harness.layer_harness import assemble, render_robust  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("layer", help="build-file relative path, e.g. layers/herd.js")
    ap.add_argument("check", nargs="?", help="check name; omit to run every check")
    ap.add_argument("--empty", action="store_true",
                    help="also score a do-nothing layer — a check the empty layer passes is not a check")
    args = ap.parse_args()

    ref = SCENES / args.scene / args.layer
    if not ref.exists():
        raise SystemExit(f"no reference layer at {ref}")

    def score(label: str, candidate: str) -> None:
        out = f"/tmp/calib-{args.scene}-{Path(candidate).stem}.cdn.html"
        assemble(args.scene, args.layer, candidate, out)
        res = render_robust(Path(out).read_text())
        print(f"\n{label}: gate {res.gate_score()} {res.gates}")
        names = [args.check] if args.check else list(CHECKS)
        for name in names:
            fn = CHECKS.get(name)
            if not fn:
                print(f"  unknown check {name}")
                continue
            try:
                ok, detail = fn(res.screenshots)
            except Exception as e:  # noqa: BLE001
                print(f"  {name}: ERROR {str(e)[:90]}")
                continue
            print(f"  {name}: {'PASS' if ok else 'FAIL'}  {json.dumps(detail)[:400]}")

    score("reference layer (must pass, with margin)", str(ref))

    if args.empty:
        import re
        cls = re.search(r"export class (\w+)", ref.read_text()).group(1)
        stub = Path(f"/tmp/empty-{cls}.js")
        stub.write_text(f"export class {cls} {{ constructor(ctx) {{}} update() {{}} }}")
        score("empty layer (must FAIL every presence check)", str(stub))

    print("\nRecord these numbers in the check's docstring. If the reference sits within ~2x of the threshold, raise the "
          "margin or measure something else — a knife-edge check produces false failures you will spend weeks chasing.")


if __name__ == "__main__":
    main()
