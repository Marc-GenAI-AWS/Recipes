#!/usr/bin/env python
"""Layer-harness wrapper — verify ONE scene layer in a frozen host (Phase 0 §4 gate 0).

Drops a candidate layer file into an otherwise-frozen reference scene, assembles
the single-file build (via scenes/assemble.cjs --set), runs the render harness
(gates: parses/runs/renders/animates/states), and adds cheap per-layer geometry
checks on the captured frames. This is the acceptance test the specialist
pipeline uses three ways: data-gen filter, training reward, loop acceptance.

  # baseline: verify the scene's own layer (should gate 1.0)
  python pipeline/harness/layer_harness.py highpark --layer layers/atmosphere.js --checks greycard

  # a candidate (model output) swapped into the frozen host
  python pipeline/harness/layer_harness.py highpark --layer layers/atmosphere.js \
      --candidate /path/to/candidate_sky.js --checks greycard

Exit code 0 iff gate_score == 1.0 and every geometry check passes.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
HARNESS_DIR = ROOT / "pipeline" / "harness"

# offline three must be ABSOLUTE (the addon route checks abspath — see PIPELINE §9)
os.environ.setdefault("HARNESS_THREE_LOCAL", str(ROOT / "vendor" / "three.module.min.js"))
os.environ.setdefault("HARNESS_THREE_ADDONS", str(ROOT / "vendor" / "three-addons"))

sys.path.insert(0, str(HARNESS_DIR))
from harness import render_and_gate  # noqa: E402

# ------------------------------------------------------------- render robustness
# SwiftShader rasterizes on the CPU and each render wants every core, so heavy
# full-screen layers (terrain) blow the harness's 10 s screenshot budget whenever
# renders overlap. A timeout under contention is load noise, not a layer verdict:
# cap machine-wide concurrent renders with file-lock slots, and re-render on timeout.
# Gate criteria are unchanged — a layer that times out on a quiet slot still fails.
RENDER_SLOTS = int(os.environ.get("RENDER_SLOTS", 2))
RENDER_LOCK_DIR = Path(os.environ.get("RENDER_LOCK_DIR", "/tmp/threejs-render-slots"))


class _RenderSlot:
    def __enter__(self):
        import fcntl
        import time
        RENDER_LOCK_DIR.mkdir(parents=True, exist_ok=True)
        while True:
            for i in range(RENDER_SLOTS):
                f = open(RENDER_LOCK_DIR / f"slot{i}", "w")
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.f = f
                    return self
                except BlockingIOError:
                    f.close()
            time.sleep(0.5)

    def __exit__(self, *exc):
        import fcntl
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


# animates by MAJORITY of states (user decision 2026-09-14): harness.py requires the whole-frame
# mean diff between shots 4 s apart > DIFF_THRESHOLD in EVERY state, and the bright, washed-out
# cloud-shadows state (~200 luma) caps calm layers below it — short stiff turf plateaued at 1.9
# while clearing 3.6-4.1 in the other states. A layer frozen in every state still fails. Applied
# here (the layer pipeline), not in harness.py (shared with the reward-function demos).
ANIMATE_MIN_STATES = int(os.environ.get("ANIMATE_MIN_STATES", 2))


def _animates_by_majority(res) -> None:
    from harness import DIFF_THRESHOLD, _mean_diff
    pairs = [s for s in res.screenshots.values() if len(s) == 2]
    moving = sum(_mean_diff(a, b) > DIFF_THRESHOLD for a, b in pairs)
    if res.gates.get("animates") or not pairs or moving < min(ANIMATE_MIN_STATES, len(pairs)):
        return
    res.gates["animates"] = True
    res.notes = [n for n in res.notes if n != "scene does not evolve over time"]
    res.notes.append(f"animates: {moving}/{len(pairs)} states move (majority rule)")


def render_robust(html: str, retries: int = 2):
    """render_and_gate inside a machine-wide render slot, re-rendering on page timeouts."""
    for attempt in range(retries + 1):
        with _RenderSlot():
            res = render_and_gate(html)
        timed_out = any(("Timeout" in str(n)) or ("unresponsive" in str(n)) for n in res.notes)
        if not timed_out or res.gate_score() == 1.0:
            break
    if attempt:
        res.notes.append(f"render attempts: {attempt + 1}")
    _animates_by_majority(res)
    return res


# ---------------------------------------------------------------- geometry checks
# Each takes {state: [png_bytes, png_bytes]} and returns (passed, detail_dict).

def _luma(png: bytes) -> float:
    return ImageStat.Stat(Image.open(io.BytesIO(png)).convert("L")).mean[0]


def check_greycard(shots: dict, lo: float = 22.0, hi: float = 242.0):
    """Exposure sanity: mean frame luminance in range for every captured state
    (catches an all-black or blown-out sky/grade)."""
    per_state, ok = {}, True
    for state, pair in shots.items():
        if not pair:
            continue
        m = _luma(pair[0])
        per_state[state] = round(m, 1)
        if not (lo <= m <= hi):
            ok = False
    return ok, {"range": [lo, hi], "mean_luma": per_state}


def check_horizon(shots: dict, min_split: float = 8.0):
    """Framing proxy: the frame has vertical structure (a sky band over a ground
    band), i.e. top-third and bottom-third mean luminance differ enough. A weak
    stand-in for a per-scene in-frame box; reports the values regardless."""
    first = next((p[0] for p in shots.values() if p), None)
    if first is None:
        return False, {"error": "no frame"}
    img = Image.open(io.BytesIO(first)).convert("L")
    w, h = img.size
    top = ImageStat.Stat(img.crop((0, 0, w, h // 3))).mean[0]
    bot = ImageStat.Stat(img.crop((0, 2 * h // 3, w, h))).mean[0]
    split = abs(top - bot)
    return (split >= min_split), {"top_luma": round(top, 1), "bottom_luma": round(bot, 1), "split": round(split, 1)}


def check_ground_detail(shots: dict, min_std: float = 6.0):
    """Ground segment: the bottom third of the frame (where the terrain sits) must
    carry real surface variation, not a flat fill — catches a ground layer that
    renders as a single unlit colour or that failed to cover the view."""
    stds, ok = {}, True
    for state, pair in shots.items():
        if not pair:
            continue
        img = Image.open(io.BytesIO(pair[0])).convert("L")
        w, h = img.size
        s = ImageStat.Stat(img.crop((0, 2 * h // 3, w, h))).stddev[0]
        stds[state] = round(s, 1)
        ok = ok and s >= min_std
    return (ok and bool(stds)), {"min_std": min_std, "bottom_std": stds}


def check_horizon_band(shots: dict, lo: float = 0.12, hi: float = 0.85, min_drop: float = 4.0,
                       min_states: int = 2):
    """Camera segment: framing sanity. The dominant sky→ground transition (largest drop in
    row-mean luminance, top to bottom) must sit in a plausible band of the frame — catches a
    camera pointed at the sky, straight down at the turf, or sitting under the terrain."""
    # calibrated 2026-09-14: real camera.js frac 0.34-0.72 / drop 21-54; sky-aimed and
    # turf-aimed rigs drop 0.6-3.1 (fail on min_drop) — hi 0.85 leaves margin for low angles.
    # A bad rig fails in every state; first-light mist can wash out the real horizon and push
    # the max drop to the bottom edge (camera-006: 0.95 / 0.30 / 0.28), so require a majority.
    fracs, good = {}, 0
    for state, pair in shots.items():
        if not pair:
            continue
        img = Image.open(io.BytesIO(pair[0])).convert("L").resize((32, 64))
        prof = [sum(img.getpixel((x, y)) for x in range(32)) / 32 for y in range(64)]
        drops = [prof[y] - prof[y + 4] for y in range(60)]
        i = max(range(60), key=lambda k: drops[k])
        frac = (i + 2) / 64
        fracs[state] = {"frac": round(frac, 2), "drop": round(drops[i], 1)}
        good += lo <= frac <= hi and drops[i] >= min_drop
    return good >= min(min_states, len(fracs)) and bool(fracs), {"band": [lo, hi], "horizon": fracs}


def check_fine_texture(shots: dict, min_hf: float = 2.5):
    """Vegetation segment: the bottom third must carry pixel-scale texture (mean 1-px horizontal
    luminance gradient) — blades, not a smooth turf fill. Calibrated 2026-09-14: real grass.js
    6.1-17.5 per state; grass removed 0.4-0.8."""
    from PIL import ImageChops
    vals, ok = {}, True
    for state, pair in shots.items():
        if not pair:
            continue
        img = Image.open(io.BytesIO(pair[0])).convert("L")
        w, h = img.size
        shifted = img.transform(img.size, Image.AFFINE, (1, 0, 1, 0, 1, 0))
        v = ImageStat.Stat(ImageChops.difference(img, shifted).crop((0, 2 * h // 3, w - 1, h))).mean[0]
        vals[state] = round(v, 2)
        ok = ok and v >= min_hf
    return (ok and bool(vals)), {"min_hf": min_hf, "bottom_hf": vals}


# ------------------------------------------------------ presence vs a layer-absent host
# Harness renders of the frozen host are deterministic (real-vs-real tile diff = 0.00 on
# the GB10, calib_presence.py 2026-09-14), so "did this layer draw anything where it
# should?" = diff against the same host with the layer replaced by a no-op class. The
# reference is rendered once and cached per CPU arch (SwiftShader floats differ x86/arm)
# and per host-scene content hash.
PRESENCE_CACHE = Path(os.environ.get("PRESENCE_CACHE", Path.home() / ".cache" / "threejs-presence"))


def _host_hash(scene: str, layer: str) -> str:
    import hashlib
    h = hashlib.sha1()
    for base in (ROOT / "scenes" / scene, ROOT / "scenes" / "contract"):
        for p in sorted(base.rglob("*.js")) + sorted(base.rglob("*.html")):
            if p != ROOT / "scenes" / scene / layer:
                h.update(str(p.relative_to(ROOT)).encode()); h.update(p.read_bytes())
    return h.hexdigest()[:12]


def reference_dir(scene: str, layer: str) -> Path:
    import platform
    return PRESENCE_CACHE / platform.machine() / scene / f"{layer.replace('/', '_')}-{_host_hash(scene, layer)}"


def layer_absent_reference(scene: str, layer: str) -> dict:
    """{state: png bytes} of the frozen host with `layer` swapped for a no-op class."""
    import fcntl
    import re
    d = reference_dir(scene, layer)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "lock", "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        if not (d / "done").exists():
            cls = re.search(r"export class (\w+)", (ROOT / "scenes" / scene / layer).read_text()).group(1)
            (d / "noop.js").write_text(f"export class {cls} {{ constructor(ctx) {{}} update() {{}} }}")
            assemble(scene, layer, str(d / "noop.js"), str(d / "build.cdn.html"))
            res = render_robust((d / "build.cdn.html").read_text())
            # the reference only needs PIXELS, not a passing scene: removing the layer legitimately breaks gates that
            # depend on it. Removing seastate's ocean leaves a sky that barely drifts, so `animates` fails — that is a
            # valid reference, not a broken render. Require only that the host still ran and produced frames.
            shots = {st: pair for st, pair in res.screenshots.items() if pair}
            if not res.gates.get("runs") or not shots:
                raise RuntimeError(f"layer-absent reference failed to render: {res.notes}")
            for st, pair in shots.items():
                (d / f"{st}.0.png").write_bytes(pair[0])
            (d / "done").write_text("ok")
    return {p.name.split(".")[0]: p.read_bytes() for p in d.glob("*.0.png")}


def _tile_diff(a_png: bytes, b_png: bytes) -> tuple[float, float]:
    """(mean, 98th-percentile) of 16x10 tile mean-abs-diffs on a 160x100 grayscale downscale."""
    from PIL import ImageChops
    small = lambda b: Image.open(io.BytesIO(b)).convert("L").resize((160, 100), Image.BILINEAR)  # noqa: E731
    diff = ImageChops.difference(small(a_png), small(b_png))
    tiles = sorted(ImageStat.Stat(diff.crop((x * 10, y * 10, x * 10 + 10, y * 10 + 10))).mean[0]
                   for y in range(10) for x in range(16))
    return sum(tiles) / len(tiles), tiles[int(0.98 * (len(tiles) - 1))]


def _diffs(shots: dict, scene: str, layer: str) -> dict:
    ref = layer_absent_reference(scene, layer)
    out = {}
    for st, pair in shots.items():
        if pair and st in ref:
            m, p = _tile_diff(pair[0], ref[st])
            out[st] = {"mean": round(m, 2), "p98": round(p, 2)}
    return out


def check_herd_presence(shots: dict, min_p98: float = 1.0, min_states: int = 2, max_mean: float = 6.0):
    """Fauna segment: the animals visibly exist in the framed meadow (p98 tile diff vs the
    herd-absent host ≥ min_p98 in ≥ min_states states) without swallowing the frame (mean ≤
    max_mean). Calibrated: real herd.js p98 3.06 / 3.08 (cloud, storm), 0.51 dawn; mean ≤ 0.85."""
    d = _diffs(shots, "highpark", "layers/herd.js")
    visible = sum(v["p98"] >= min_p98 for v in d.values())
    ok = visible >= min_states and all(v["mean"] <= max_mean for v in d.values())
    return ok, {"min_p98": min_p98, "min_states": min_states, "max_mean": max_mean, "vs_absent": d}


def check_mist_gating(shots: dict, min_on_p98: float = 8.0, max_off_mean: float = 2.5):
    """Effects segment: the mist is clearly visible at dawn (cur.mist = 1, p98 tile diff vs the
    mist-absent host ≥ min_on_p98) and effectively gone in cloud-shadows (cur.mist = 0, mean ≤
    max_off_mean). Calibrated: real mist.js first-light p98 37.5; cloud-shadows mean 0.21."""
    d = _diffs(shots, "highpark", "layers/mist.js")
    on, off = d.get("first-light"), d.get("cloud-shadows")
    ok = bool(on and off) and on["p98"] >= min_on_p98 and off["mean"] <= max_off_mean
    return ok, {"min_on_p98": min_on_p98, "max_off_mean": max_off_mean, "vs_absent": d}


def check_sky_presence(shots: dict, min_top: float = 20.0):
    """Sky segment: the dome is actually drawn — top-third mean diff vs the dome-absent host ≥
    min_top in EVERY state. A dome that never writes gl_FragColor compiles clean, passes the
    gates, greycard and horizon, and renders identically to no dome (diff 0.0). Calibrated
    2026-09-14: real atmosphere.js 170-215; black spec sky-002 0.0 / 0.0 / 0.0; same with
    gl_FragColor added 194-218."""
    from PIL import ImageChops
    ref = layer_absent_reference("highpark", "layers/atmosphere.js")
    small = lambda b: Image.open(io.BytesIO(b)).convert("L").resize((160, 100), Image.BILINEAR)  # noqa: E731
    tops = {st: round(ImageStat.Stat(ImageChops.difference(small(pair[0]), small(ref[st])).crop((0, 0, 160, 33))).mean[0], 2)
            for st, pair in shots.items() if pair and st in ref}
    return bool(tops) and all(v >= min_top for v in tops.values()), {"min_top": min_top, "top_vs_absent": tops}


def check_water_presence(shots: dict, min_mean: float = 8.0, min_bottom_std: float = 4.0):
    """Ocean segment (seastate host): the water actually covers the lower view. Mean diff vs the ocean-absent host in
    EVERY state (an absent surface renders identically, diff 0), plus real variation in the bottom third so a flat unlit
    fill does not pass. Uses the frame mean rather than a tile percentile: the sea fills most of the frame, so the
    compact-object rule that herd_presence needs does not apply here."""
    d = _diffs(shots, "seastate", "layers/ocean.js")
    stds, ok = {}, bool(d) and all(v["mean"] >= min_mean for v in d.values())
    for state, pair in shots.items():
        if not pair:
            continue
        img = Image.open(io.BytesIO(pair[0])).convert("L")
        w, h = img.size
        s = ImageStat.Stat(img.crop((0, 2 * h // 3, w, h))).stddev[0]
        stds[state] = round(s, 1)
        ok = ok and s >= min_bottom_std
    return ok, {"min_mean": min_mean, "min_bottom_std": min_bottom_std, "vs_absent": d, "bottom_std": stds}


CHECKS = {"greycard": check_greycard, "horizon": check_horizon,
          "ground_detail": check_ground_detail, "horizon_band": check_horizon_band,
          "fine_texture": check_fine_texture, "herd_presence": check_herd_presence,
          "mist_gating": check_mist_gating, "sky_presence": check_sky_presence,
          "water_presence": check_water_presence}


# ---------------------------------------------------------------------------- run

def assemble(scene: str, layer: str | None, candidate: str | None, out: str) -> None:
    cmd = ["node", str(ROOT / "scenes" / "assemble.cjs"), scene]
    if layer and candidate:
        cmd += ["--set", f"{layer}={os.path.abspath(candidate)}"]
    cmd += ["--out", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"assemble failed:\n{r.stdout}\n{r.stderr}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify one scene layer in a frozen host.")
    ap.add_argument("scene")
    ap.add_argument("--layer", help="build-file relpath to swap, e.g. layers/atmosphere.js")
    ap.add_argument("--candidate", help="candidate layer file (omit for baseline = the scene's own layer)")
    ap.add_argument("--checks", default="", help="comma list: greycard,horizon")
    ap.add_argument("--out", help="assembled html path (default: a temp file)")
    ap.add_argument("--keep", action="store_true", help="keep the assembled html")
    args = ap.parse_args()

    tmp = args.out or tempfile.mktemp(prefix=f"lh_{args.scene}_", suffix=".cdn.html")
    assemble(args.scene, args.layer, args.candidate, tmp)

    html = Path(tmp).read_text()
    res = render_robust(html)   # same render slots + animates majority rule as the pipeline
    gate = res.gate_score()

    checks_out, checks_pass = {}, True
    for cname in [c for c in args.checks.split(",") if c]:
        fn = CHECKS.get(cname)
        if fn is None:
            checks_out[cname] = {"error": "unknown check"}
            checks_pass = False
            continue
        ok, detail = fn(res.screenshots)
        checks_out[cname] = {"pass": ok, **detail}
        checks_pass = checks_pass and ok

    passed = gate == 1.0 and checks_pass
    report = {
        "scene": args.scene, "layer": args.layer,
        "candidate": args.candidate or "(baseline: scene's own layer)",
        "gate_score": gate, "gates": res.gates, "notes": res.notes,
        "states": res.states, "checks": checks_out, "pass": passed,
        "html": tmp if (args.keep or args.out) else None,
    }
    print(json.dumps(report, indent=2))
    if not (args.keep or args.out):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
