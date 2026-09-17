"""Preview the judge's sky-view capture before paying for any judge calls.

Renders a sky candidate (or the host's own sky) into High Park with the sky-view camera,
no mist and no rain, and saves the frames for a human look.

  python scenes/phase1/judge_view/preview_skyview.py original phase1/sky_baseline_fable2/cand-sky-010.js
  -> /tmp/skyview/<name>-<state>.png
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scenes"))
from layer_harness import render_robust  # noqa: E402

OUT = Path("/tmp/skyview")


def build_skyview(candidate: str | None, out: Path) -> None:
    cmd = ["node", str(REPO / "scenes" / "assemble.cjs"), "highpark",
           "--set", f"camera.js={HERE / 'skyview_camera.js'}",
           "--set", f"layers/mist.js={HERE / 'noop_mist.js'}",
           "--set", f"layers/rain.js={HERE / 'noop_rain.js'}"]
    if candidate:
        cmd += ["--set", f"layers/atmosphere.js={Path(candidate).resolve()}"]
    cmd += ["--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for arg in sys.argv[1:]:
        name = "original" if arg == "original" else Path(arg).stem
        build = OUT / f"{name}.cdn.html"
        build_skyview(None if arg == "original" else str(REPO / arg), build)
        res = render_robust(build.read_text())
        for st, pair in res.screenshots.items():
            if pair:
                (OUT / f"{name}-{st}.png").write_bytes(pair[0])
        print(name, "gate", res.gate_score(), res.notes[:1], sorted(res.screenshots), flush=True)


if __name__ == "__main__":
    main()
