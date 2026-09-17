"""Render a host scene untouched and report the gates — the first thing to run when adding a new scene.

The gates (parses / runs / renders / animates / states) are scene-agnostic, so a host that renders here needs no harness
changes. If this fails, fix the host before writing any contract: everything downstream compares against it.

  python scripts/render_host.py seastate
  python scripts/render_host.py seastate --shots /tmp/seastate     # also write the captured frames
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.harness.layer_harness import assemble, render_robust  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--shots", help="directory to write the captured frames into")
    args = ap.parse_args()

    out = f"/tmp/host-{args.scene}.cdn.html"
    assemble(args.scene, None, None, out)
    html = Path(out).read_text()
    print(f"assembled {len(html):,} bytes -> {out}")

    res = render_robust(html)
    print(f"gate {res.gate_score()}  {res.gates}")
    print(f"states captured: {list(res.screenshots)}")
    for n in res.notes[:4]:
        print("  note:", str(n)[:200])

    if args.shots:
        d = Path(args.shots)
        d.mkdir(parents=True, exist_ok=True)
        for state, pair in res.screenshots.items():
            if pair:
                (d / f"{state}.png").write_bytes(pair[0])
        print(f"wrote frames to {d}")

    if res.gate_score() < 1.0:
        print("\nThe host does not pass on its own. Fix that first — a layer cannot be verified against a broken host.")
        raise SystemExit(1)
    print("\nHost is sound. Next: write the brief sampler and contract (docs/ADDING_A_SCENE.md).")


if __name__ == "__main__":
    main()
