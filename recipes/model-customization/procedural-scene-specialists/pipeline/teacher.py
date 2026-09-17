"""Generic per-segment generate → verify → (critique-and-revise) runner.

Same loop that produced the sky results (gen_sky_baseline.py, left untouched for
reproducibility), parameterized by the segment registry. Reuses its model plumbing
(Bedrock Fable / OpenAI-compatible endpoint, reviser, pricing).

  # teacher ceiling on the held-out eval set
  python pipeline/teacher.py --segment ground --tag fable --seed 1 --n 24
  # r4 / a specialist served locally
  python pipeline/teacher.py --segment ground --generator r4 --endpoint http://localhost:8001/v1 --gen-model r4 --tag r4
  # training data / CaR
  python pipeline/teacher.py --segment ground --tag train --seed 2 --n 96
  python pipeline/teacher.py --segment ground --generator sky --gen-model ground --reviser fable --tag car --seed 3 --n 96

Outputs data/<segment>_<tag>/{log.jsonl, summary.json, cand-*.js, build-*.cdn.html}.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import gen_sky_baseline as gsb  # noqa: E402  (model plumbing: converse, revise, pricing, FENCE)
from layer_harness import assemble, CHECKS, render_robust  # noqa: E402
from segments import SEGMENTS  # noqa: E402

SEG: dict = {}


def verify(cid: str, js: str, out: Path, brief: str = "") -> dict:
    cand = out / f"cand-{cid}.js"
    cand.write_text(js)
    build = out / f"build-{cid}.cdn.html"
    assemble(SEG["scene"], SEG["layer"], str(cand), str(build))
    res = render_robust(build.read_text())
    gate = res.gate_score()
    checks, ok = {}, gate == 1.0
    notes = res.notes[:2]
    for name in SEG["checks"]:
        if name == "brief_judge":
            continue
        c_ok, detail = CHECKS[name](res.screenshots)
        checks[name] = {"pass": c_ok, **detail}
        ok = ok and c_ok
    judge_cost = 0.0
    # brief adherence (Fable vision judge) runs last and only on otherwise-passing layers: it is
    # the one paid check, and "renders + present" is a precondition for judging what it shows
    if ok and "brief_judge" in SEG["checks"]:
        from brief_judge import judge_brief, skyview_shots
        # sky is judged from a sky-facing render; in the scene camera's frames any sky reads as haze
        shots = skyview_shots(str(cand)) if SEG["name"] == "sky" else res.screenshots
        j_ok, jd = judge_brief(SEG["name"], brief, shots)
        checks["brief_judge"] = {"pass": j_ok, **jd}
        judge_cost = jd.get("cost", 0.0)
        ok = j_ok
        if not j_ok:
            notes = notes + [f"brief judge (scores 0-3 per clause {jd.get('scores')}): {jd.get('most_wrong', '')}"]
    return {"gate": gate, "gates": res.gates, "notes": notes, "checks": checks, "pass": ok,
            "judge_cost": judge_cost}


def extract(text: str) -> str:
    m = gsb.FENCE.search(text)
    return m.group(1).strip() if m else text.strip()


# Bedrock capacity blips (Fable ServiceUnavailableException under ~20 concurrent calls,
# 2026-09-14) outlast boto's 3 adaptive retries; back off for minutes, not seconds.
TRANSIENT = ("ServiceUnavailable", "Throttl", "ModelNotReady", "InternalServer", "timed out", "Read timeout")


def with_backoff(fn, *a, tries: int = 6):
    import random
    for k in range(tries):
        try:
            return fn(*a)
        except Exception as e:  # noqa: BLE001
            if k == tries - 1 or not any(s in str(e) for s in TRANSIENT):
                raise
            time.sleep(min(300, 20 * 2 ** k) * (0.7 + 0.6 * random.random()))


# What to tell the reviser when a render CHECK (not a console error) fails. Without this the repair prompt
# said only "(no harness notes; a visual check failed)", so e.g. Fable could not fix an invisible herd.
CHECK_HINTS = {
    "herd_presence": "the herd is not visible from the host camera — the frame barely differs from the scene "
                     "without your layer. Place the animals within ~30 units of (12, -46) at y = groundH(x, z), "
                     "make sure every mesh reaches ctx.scene through its group, and size them to be clearly visible.",
    "fine_texture": "the lower third of the frame shows no blade-level detail — use thin blades with per-blade "
                    "tone variation so individual blades read near the camera.",
    "mist_gating": "the mist must be clearly visible at first light (uMist = 1) and vanish in cloud-shadows "
                   "(uMist = 0) — multiply alpha by uMist and give it enough opacity to show.",
    "sky_presence": "the sky dome is not drawn — it renders identically to no dome; assign gl_FragColor before TAIL.",
    "ground_detail": "the ground is too flat in the lower frame — vary the turf tone (e.g. fbm2 over p.xz).",
    "horizon_band": "the framing puts the horizon too high or too low — keep the sky/ground line in the middle band.",
    "greycard": "the frame is too dark or blown out overall.",
    "horizon": "the frame lacks a clear sky-over-ground split.",
}


def repair_notes(v: dict) -> str:
    lines = list(v.get("notes") or [])
    for name, c in (v.get("checks") or {}).items():
        if not c.get("pass") and name != "brief_judge":
            detail = {k: val for k, val in c.items() if k != "pass"}
            lines.append(f"check '{name}' failed: {CHECK_HINTS.get(name, 'a visual check failed')} "
                         f"(measured: {json.dumps(detail)[:220]})")
    return "\n".join(f"- {n}" for n in (lines or ["(no harness notes; a visual check failed)"]))


def process(brief: dict, out: Path) -> dict:
    t0 = time.time()
    bt = SEG["briefs"].brief_text(brief)
    rec = {"id": brief["id"], "brief": bt, "cost": 0.0}
    cls = f"class {SEG['class_name']}"
    try:
        text, usage = with_backoff(gsb.converse, SEG["prompt"].replace("{brief}", bt), SEG.get("max_tokens", 8000))
        rec["cost"] = round(gsb.price(usage), 4)
        rec["out_tokens"] = usage.get("outputTokens", 0)
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"generate: {str(e)[:160]}"
        return rec
    js = extract(text)
    if cls not in js:
        rec["error"] = f"no `{cls}` in output"
        rec["raw"] = text[:400]
        return rec
    try:
        v = verify(brief["id"], js, out, bt)
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"verify: {str(e)[:200]}"
        return rec
    rec.update(v); rec["attempts"] = 1
    rec["cost"] = round(rec["cost"] + v["judge_cost"], 4)
    if not v["pass"]:
        try:
            notes = repair_notes(v)
            prompt = (SEG["repair"].replace("{layer_name}", SEG["layer_name"])
                      .replace("{notes}", notes).replace("{js}", js))
            rtext, rusage = with_backoff(gsb.revise, prompt, SEG.get("max_tokens", 8000))
            rec["cost"] = round(rec["cost"] + gsb.revise_cost(rusage), 4)
            js2 = extract(rtext)
            if cls in js2:
                v2 = verify(brief["id"] + "-rev", js2, out, bt)
                rec["cost"] = round(rec["cost"] + v2["judge_cost"], 4)
                rec["attempts"] = 2; rec["revise_gate"] = v2["gate"]; rec["revise_pass"] = v2["pass"]
                if v2["pass"]:
                    rec.update(v2); rec["revised"] = True
        except Exception as e:  # noqa: BLE001
            rec["revise_error"] = str(e)[:150]
    rec["seconds"] = round(time.time() - t0)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True, choices=sorted(SEGMENTS))
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="fable")
    ap.add_argument("--generator", default="fable")
    ap.add_argument("--endpoint", default="http://localhost:8001/v1")
    ap.add_argument("--gen-model", default="r4")
    ap.add_argument("--reviser", default=None)
    args = ap.parse_args()

    SEG.update(SEGMENTS[args.segment]); SEG["name"] = args.segment
    gsb.GENERATOR, gsb.ENDPOINT, gsb.GEN_MODEL = args.generator, args.endpoint, args.gen_model
    gsb.REVISER = args.reviser or args.generator

    briefs = SEG["briefs"].sample(args.n, args.seed)
    out = REPO / "phase1" / f"{args.segment}_{args.tag}"
    out.mkdir(parents=True, exist_ok=True)
    log = out / "log.jsonl"
    # a transient generate failure is not a verdict: those ids are retried on resume
    prior = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    done = {r["id"] for r in prior if not str(r.get("error", "")).startswith("generate:")}
    todo = [b for b in briefs if b["id"] not in done][: args.limit]
    print(f"segment={args.segment} tag={args.tag} generator={gsb.GENERATOR} reviser={gsb.REVISER}: "
          f"{len(briefs)} briefs, {len(done)} done, {len(todo)} to do", flush=True)

    passed, cost = 0, 0.0
    with log.open("a") as f, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process, b, out): b for b in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            f.write(json.dumps(rec) + "\n"); f.flush()
            passed += 1 if rec.get("pass") else 0
            cost += rec.get("cost", 0.0)
            status = (f"ERR {rec['error'][:70]}" if rec.get("error") else
                      f"gate {rec['gate']} checks={ {k: v['pass'] for k, v in rec.get('checks', {}).items()} } "
                      f"{'PASS' if rec.get('pass') else 'fail'}{' (rev)' if rec.get('revised') else ''}")
            print(f"  [{n}/{len(todo)}] {rec['id']} {status} ${rec.get('cost', 0):.3f} "
                  f"({rec.get('seconds', '?')}s) | pass {passed} ${cost:.2f}", flush=True)

    latest = {}
    for line in log.read_text().splitlines():   # a retried id appends a newer row; last row wins
        r = json.loads(line); latest[r["id"]] = r
    rows = list(latest.values())
    ok = [r for r in rows if r.get("pass")]
    summary = {"segment": args.segment, "tag": args.tag, "generator": gsb.GENERATOR,
               "briefs": len(rows), "pass": len(ok), "pass_rate": round(len(ok) / max(1, len(rows)), 3),
               "first_shot_pass": sum(1 for r in ok if not r.get("revised")),
               "total_cost": round(sum(r.get("cost", 0.0) for r in rows), 2),
               "errors": [r["id"] for r in rows if r.get("error")]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print("SEGMENT-RUN-DONE:", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
