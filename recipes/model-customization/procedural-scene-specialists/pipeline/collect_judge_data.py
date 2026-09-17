"""Collect brief-judge training data: (rendered frames + brief) -> Opus's per-clause scores.

Samples layers from the raw generation runs, re-renders them for frames, and asks the Opus judge to score each clause.
Two kinds of row, because a judge trained only on matching pairs never learns to say no:
  match     the layer judged against its OWN brief
  mismatch  the same frames judged against a DIFFERENT layer's brief from the same segment (calibration showed Opus
            scores these near 0 and names the contradiction, so they are reliable negatives)

Rows are written in the shape TRL's vision SFT expects: an `images` list plus prompt/completion message lists. The prompt
text is built by brief_judge itself, so training and inference see the identical rubric.

  python pipeline/collect_judge_data.py --n 300 --mismatch-frac 0.4 --out data/judge_data
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import brief_judge as bj  # noqa: E402
from layer_harness import assemble, render_robust  # noqa: E402
from segments import SEGMENTS  # noqa: E402


def candidates(seg: str, runs_root: Path) -> list[dict]:
    """Every renderable layer we have for a segment, with its brief and source file.

    runs_root is scanned RECURSIVELY for <segment>_<tag>/log.jsonl: locally that is phase1/, but on a SageMaker job the
    runs are pulled from S3 where each one nests as <seg>_<tag>/data/<seg>_<tag>/log.jsonl.
    """
    out = []
    seen = set()
    for log in sorted(runs_root.glob(f"**/{seg}_*/log.jsonl")):
        run = log.parent
        if run.name in seen:            # the S3 layout repeats the run name; keep the deepest copy only
            continue
        seen.add(run.name)
        rows = {}
        for line in log.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            rows[r.get("id")] = r
        for r in rows.values():
            if r.get("gate") != 1.0 or not r.get("brief"):
                continue
            cand = run / (f"cand-{r['id']}-rev.js" if r.get("revised") else f"cand-{r['id']}.js")
            if cand.exists():
                out.append({"segment": seg, "run": run.name, "id": r["id"], "brief": r["brief"], "cand": str(cand)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="layers to render (each yields 1 match row)")
    ap.add_argument("--mismatch-frac", type=float, default=0.4, help="share of rendered layers also judged vs a wrong brief")
    ap.add_argument("--segments", default="sky,ground,camera,vegetation,fauna,effects,ocean")
    ap.add_argument("--out", default="data/judge_data")
    ap.add_argument("--runs-dir", default=None, help="root holding the raw generation runs (default: phase1/)")
    ap.add_argument("--workers", type=int, default=4, help="parallel render+judge workers")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    runs_root = Path(args.runs_dir) if args.runs_dir else REPO / "phase1"
    segs = [s for s in args.segments.split(",") if s in SEGMENTS]
    pools = {s: candidates(s, runs_root) for s in segs}
    if not any(pools.values()):
        raise SystemExit(f"no runs found under {runs_root} — nothing to judge")
    rng = random.Random(args.seed)
    picked = []
    per_seg = max(1, args.n // max(1, len(segs)))
    for s in segs:
        pool = pools[s]
        rng.shuffle(pool)
        picked += pool[:per_seg]
    rng.shuffle(picked)
    picked = picked[: args.n]
    print(f"pools: { {s: len(p) for s, p in pools.items()} } -> sampling {len(picked)}", flush=True)

    out = REPO / args.out
    (out / "frames").mkdir(parents=True, exist_ok=True)
    rows_path = out / "rows.jsonl"
    done = set()
    if rows_path.exists():                       # resumable: re-running tops up rather than starting over
        for line in rows_path.read_text().splitlines():
            try:
                done.add(json.loads(line)["key"])
            except Exception:  # noqa: BLE001
                pass
    print(f"{len(done)} rows already collected", flush=True)

    lock = __import__("threading").Lock()
    stats = {"rendered": 0, "match": 0, "mismatch": 0, "cost": 0.0, "skipped": 0}

    def work(item: dict):
        seg = item["segment"]
        keys = [f"{item['run']}/{item['id']}/match"]
        if rng.random() < args.mismatch_frac:
            keys.append(f"{item['run']}/{item['id']}/mismatch")
        if all(k in done for k in keys):
            return
        spec = SEGMENTS[seg]
        build = f"/tmp/judgedata-{seg}-{item['id']}.cdn.html"
        try:
            assemble(spec["scene"], spec["layer"], item["cand"], build)
            res = render_robust(Path(build).read_text())
        except Exception as e:  # noqa: BLE001
            with lock:
                stats["skipped"] += 1
            print(f"  skip {item['id']}: {str(e)[:80]}", flush=True)
            return
        if res.gate_score() < 1.0:
            with lock:
                stats["skipped"] += 1
            return
        # sky must be judged from the sky-view camera, as gen_segment.verify does: in the scene camera's frames the sky is
        # a thin hazy band and even the real High Park dome scores ~0-1, so scene-camera sky rows carry no signal at all
        if seg == "sky":
            try:
                shots = {st: pair for st, pair in bj.skyview_shots(item["cand"]).items() if pair}
            except Exception as e:  # noqa: BLE001
                print(f"  skyview failed {item['id']}: {str(e)[:80]}", flush=True)
                with lock:
                    stats["skipped"] += 1
                return
        else:
            shots = {st: pair for st, pair in res.screenshots.items() if pair}
        stem = f"{seg}-{item['run']}-{item['id']}"
        paths = []
        order = [st for st in bj.STATES if st in shots] or sorted(shots)[:3]
        for st in order[:3]:
            p = out / "frames" / f"{stem}-{st}.jpg"
            p.write_bytes(bj._jpeg(shots[st][0], w=800))
            paths.append(str(p.relative_to(REPO)))
        with lock:
            stats["rendered"] += 1

        for kind, key in zip(("match", "mismatch"), keys):
            if key in done:
                continue
            brief = item["brief"]
            if kind == "mismatch":
                others = [c for c in pools[seg] if c["id"] != item["id"] and c["brief"] != item["brief"]]
                if not others:
                    continue
                brief = rng.choice(others)["brief"]
            try:
                ok, d = bj.judge_brief(seg, brief, shots)
            except Exception as e:  # noqa: BLE001
                print(f"  judge failed {item['id']} {kind}: {str(e)[:90]}", flush=True)
                continue
            if "scores" not in d:
                continue
            scene_desc, states_desc, layer_desc = bj.describe(seg, shots)
            cl = bj.clauses(brief)
            rubric = bj.RUBRIC.format(scene=scene_desc, states=states_desc, layer=layer_desc,
                                      clauses="\n".join(f"- {k}: {v}" for k, v in cl.items()))
            target = json.dumps({"scores": d["scores"], "most_wrong": d.get("most_wrong", "")}, indent=None)
            row = {"key": key, "segment": seg, "kind": kind, "id": item["id"], "run": item["run"],
                   "images": paths, "pass": bool(ok), "mean": d.get("mean"),
                   "prompt": [{"role": "user", "content": [{"type": "image"}] * len(paths)
                               + [{"type": "text", "text": rubric}]}],
                   "completion": [{"role": "assistant", "content": [{"type": "text", "text": target}]}]}
            with lock:
                with rows_path.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                stats[kind] += 1
                stats["cost"] += d.get("cost", 0.0)
                done.add(key)
        with lock:
            print(f"  [{stats['match'] + stats['mismatch']} rows | rendered {stats['rendered']} | "
                  f"${stats['cost']:.2f}] {seg} {item['id']}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(work, picked))
    print(f"JUDGE-DATA-DONE {json.dumps(stats)} in {round(time.time() - t0)}s -> {rows_path}", flush=True)


if __name__ == "__main__":
    main()
