"""Director loop: a plan of per-segment briefs -> fine-tuned specialists write each layer -> the layer harness verifies
each one in the frozen host -> accepted layers are composed into one self-contained scene .cdn.html.

Per segment: up to --attempts generations (temperature 0.7) from that segment's specialist; a failing generation gets one
self-repair from the same specialist using the harness notes. The first layer that passes the segment's gates and checks
is accepted. If none pass, the scene keeps the host's own layer for that segment and the report says so.

Fauna presence defaults to the mean-based rule (frame-mean diff vs the herd-absent host >= 0.05 in >= 2 states): the p98
tile rule fails compact herds that are plainly visible (data/herd_visual_check/, 2026-09-15).

  python pipeline/director.py --plans data/plans/demo.json --out phase1/director_demo \
      --endpoint sky=http://localhost:8001/v1 ... --endpoint fauna=http://localhost:8002/v1

Writes <out>/<scene id>/{plan.json, <segment>.js, scene.cdn.html, shot-<state>.png, report.json} and <out>/summary.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import gen_segment as gs  # noqa: E402  (extract, repair_notes, with_backoff)
from layer_harness import CHECKS, _diffs, assemble, render_robust  # noqa: E402
from segments import SEGMENTS  # noqa: E402

SEGMENT_ORDER = ["sky", "ground", "camera", "vegetation", "fauna", "effects"]


# Layers are verified one at a time in the default host, so nothing catches a combination that reads badly: scene-001 of the
# first demo run passed every gate with a pale ground under dense mist and washed out near-white (luma 198/228/191, ground
# brighter than sky). These composite checks run on the assembled scene; the segments most able to fix it are regenerated.
COMPOSITE_CULPRITS = ["ground", "effects", "camera"]
COMPOSITE_HINT = ("Note: in the assembled scene this layer combined into a washed-out, near-white frame — {detail}. "
                  "Keep the ground clearly darker than the sky, keep haze/mist thin enough that the terrain and peaks stay "
                  "readable, and keep the horizon split visible.")


def composite_check(res, max_luma: float = 215.0, min_bright_states: int = 2):
    """Does the assembled scene read as a scene? greycard + horizon, plus a washout rule."""
    detail = {}
    ok = True
    for name in ("greycard", "horizon"):
        c_ok, d = CHECKS[name](res.screenshots)
        detail[name] = {"pass": c_ok, **d}
        ok = ok and c_ok
    lumas = detail["greycard"].get("mean_luma", {})
    inverted = detail["horizon"].get("bottom_luma", 0) > detail["horizon"].get("top_luma", 0)
    too_bright = sum(v > max_luma for v in lumas.values()) >= min_bright_states
    detail["washout"] = {"pass": not (inverted or too_bright), "inverted_horizon": inverted,
                         "bright_states": [st for st, v in lumas.items() if v > max_luma], "max_luma": max_luma}
    reasons = ([f"the ground ({detail['horizon'].get('bottom_luma')}) is brighter than the sky ({detail['horizon'].get('top_luma')})"] if inverted else []) \
        + ([f"states {detail['washout']['bright_states']} are near-white (mean luma over {max_luma})"] if too_bright else []) \
        + [f"the composite {n} check failed" for n in ("greycard", "horizon") if not detail[n]["pass"]]
    return (ok and not (inverted or too_bright)), detail, "; ".join(reasons)


def herd_presence_mean(shots: dict, min_mean: float = 0.05, min_states: int = 2, max_mean: float = 6.0):
    d = _diffs(shots, "highpark", "layers/herd.js")
    ok = sum(v["mean"] >= min_mean for v in d.values()) >= min_states and all(v["mean"] <= max_mean for v in d.values())
    return ok, {"rule": "mean", "min_mean": min_mean, "min_states": min_states, "vs_absent": d}


def chat(endpoint: str, model: str, text: str, max_tokens: int) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": text}], "max_tokens": max_tokens,
                       "temperature": 0.7, "top_p": 0.8, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def verify(seg_name: str, js: str, path: Path, herd_rule: str) -> dict:
    seg = SEGMENTS[seg_name]
    path.write_text(js)
    build = path.with_suffix(".cdn.html")
    assemble(seg["scene"], seg["layer"], str(path), str(build))
    res = render_robust(build.read_text())
    ok, checks = res.gate_score() == 1.0, {}
    for name in seg["checks"]:
        fn = herd_presence_mean if (name == "herd_presence" and herd_rule == "mean") else CHECKS[name]
        c_ok, detail = fn(res.screenshots)
        checks[name] = {"pass": c_ok, **detail}
        ok = ok and c_ok
    build.unlink(missing_ok=True)
    return {"gate": res.gate_score(), "notes": res.notes[:3], "checks": checks, "pass": ok}


def run_segment(seg_name: str, brief: str, endpoint: str, model: str, attempts: int, scene_dir: Path, herd_rule: str) -> dict:
    seg = SEGMENTS[seg_name]
    cls, max_tokens = f"class {seg['class_name']}", seg.get("max_tokens", 8000)
    work = scene_dir / "attempts"
    work.mkdir(exist_ok=True)
    log = []
    for a in range(attempts):
        t0 = time.time()
        try:
            js = gs.extract(chat(endpoint, model, seg["prompt"].replace("{brief}", brief), max_tokens))
        except Exception as e:  # noqa: BLE001
            log.append({"attempt": a, "error": f"generate: {str(e)[:160]}"}); continue
        if cls not in js:
            log.append({"attempt": a, "error": f"no `{cls}` in output"}); continue
        v = verify(seg_name, js, work / f"{seg_name}-{a}.js", herd_rule)
        entry = {"attempt": a, "gate": v["gate"], "pass": v["pass"], "notes": v["notes"],
                 "failed_checks": [k for k, c in v["checks"].items() if not c["pass"]], "seconds": round(time.time() - t0)}
        if not v["pass"]:
            repair = (seg["repair"].replace("{layer_name}", seg["layer_name"])
                      .replace("{notes}", gs.repair_notes(v)).replace("{js}", js))
            try:
                js2 = gs.extract(chat(endpoint, model, repair, max_tokens))
                if cls in js2:
                    v2 = verify(seg_name, js2, work / f"{seg_name}-{a}-rev.js", herd_rule)
                    entry.update({"revise_gate": v2["gate"], "revise_pass": v2["pass"]})
                    if v2["pass"]:
                        js, v = js2, v2
            except Exception as e:  # noqa: BLE001
                entry["revise_error"] = str(e)[:160]
        log.append(entry)
        if v["pass"]:
            (scene_dir / f"{seg_name}.js").write_text(js)
            return {"segment": seg_name, "accepted": True, "attempts": log, "checks": v["checks"]}
    return {"segment": seg_name, "accepted": False, "attempts": log}


def compose(scene_dir: Path, accepted: list[str]) -> Path:
    out = scene_dir / "scene.cdn.html"
    cmd = ["node", str(REPO / "scenes" / "assemble.cjs"), "highpark"]
    for seg_name in accepted:
        cmd += ["--set", f"{SEGMENTS[seg_name]['layer']}={(scene_dir / f'{seg_name}.js').resolve()}"]
    cmd += ["--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"compose failed:\n{r.stdout}\n{r.stderr}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--endpoint", action="append", default=[], help="segment=http://host:port/v1 (one per segment)")
    ap.add_argument("--model", action="append", default=[], help="segment=served model name (default: the segment name)")
    ap.add_argument("--segments", default=",".join(SEGMENT_ORDER), help="segments to generate; others keep the host layer")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--herd-rule", choices=["mean", "p98"], default="mean")
    ap.add_argument("--composite-rounds", type=int, default=2,
                    help="times to regenerate ground/mist/camera when the assembled scene fails the composite check")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    endpoints = dict(e.split("=", 1) for e in args.endpoint)
    models = dict(m.split("=", 1) for m in args.model)
    wanted = [s for s in args.segments.split(",") if s]
    missing = [s for s in wanted if s not in endpoints]
    if missing:
        ap.error(f"no --endpoint for {missing}")
    plans = json.loads(Path(args.plans).read_text())["scenes"][: args.limit]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    summary = []
    for sc in plans:
        scene_dir = out / sc["id"]
        scene_dir.mkdir(parents=True, exist_ok=True)
        (scene_dir / "plan.json").write_text(json.dumps(sc, indent=2))
        t0 = time.time()
        print(f"== {sc['id']}: {sc['theme']}", flush=True)
        with ThreadPoolExecutor(len(wanted)) as ex:
            futs = {s: ex.submit(run_segment, s, sc["briefs"][s], endpoints[s], models.get(s, s), args.attempts,
                                 scene_dir, args.herd_rule) for s in wanted}
            results = {s: f.result() for s, f in futs.items()}
        for s in wanted:
            r = results[s]
            n_try = len(r["attempts"])
            print(f"   {s:10s} {'ACCEPTED' if r['accepted'] else 'host fallback'} after {n_try} attempt(s)", flush=True)
        accepted = [s for s in wanted if results[s]["accepted"]]
        html = compose(scene_dir, accepted)
        final = render_robust(html.read_text())
        comp_ok, comp_detail, comp_why = composite_check(final)
        rounds = [{"round": 0, "pass": comp_ok, "why": comp_why, "detail": comp_detail}]
        print(f"   composite check: {'PASS' if comp_ok else 'FAIL — ' + comp_why}", flush=True)
        for rnd in range(1, args.composite_rounds + 1):
            if comp_ok:
                break
            culprits = [s for s in COMPOSITE_CULPRITS if s in accepted]
            print(f"   composite round {rnd}: regenerating {culprits}", flush=True)
            hint = COMPOSITE_HINT.format(detail=comp_why)
            with ThreadPoolExecutor(max(1, len(culprits))) as ex:
                futs = {s: ex.submit(run_segment, s, sc["briefs"][s] + "\n" + hint, endpoints[s], models.get(s, s),
                                     args.attempts, scene_dir, args.herd_rule) for s in culprits}
                redone = {s: f.result() for s, f in futs.items()}
            for s, r in redone.items():          # a failed retry keeps the layer that already passed its own checks
                results[s] = {**r, "composite_round": rnd} if r["accepted"] else results[s]
            html = compose(scene_dir, accepted)
            final = render_robust(html.read_text())
            comp_ok, comp_detail, comp_why = composite_check(final)
            rounds.append({"round": rnd, "regenerated": [s for s, r in redone.items() if r["accepted"]],
                           "pass": comp_ok, "why": comp_why, "detail": comp_detail})
            print(f"   composite check after round {rnd}: {'PASS' if comp_ok else 'FAIL — ' + comp_why}", flush=True)
        for state, pair in final.screenshots.items():
            if pair:
                (scene_dir / f"shot-{state}.png").write_bytes(pair[0])
        report = {"id": sc["id"], "theme": sc["theme"], "briefs": sc["briefs"], "accepted": accepted,
                  "host_fallback": [s for s in SEGMENT_ORDER if s not in accepted],
                  "final_gate": final.gate_score(), "final_gates": final.gates, "final_notes": final.notes[:4],
                  "composite_pass": comp_ok, "composite_rounds": rounds,
                  "segments": results, "herd_rule": args.herd_rule, "seconds": round(time.time() - t0)}
        (scene_dir / "report.json").write_text(json.dumps(report, indent=2))
        summary.append({k: report[k] for k in ("id", "theme", "accepted", "host_fallback", "final_gate", "seconds")})
        print(f"   composed {html} | final gate {final.gate_score()} | {len(accepted)}/{len(SEGMENT_ORDER)} specialist layers "
              f"| {report['seconds']}s", flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print("DIRECTOR-DONE:", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
