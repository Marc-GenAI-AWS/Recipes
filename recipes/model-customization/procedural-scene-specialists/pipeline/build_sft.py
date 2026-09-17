"""Build an SFT dataset for any segment from its verified generations.

Reads data/<segment>_train/ (teacher set) and, if present, data/<segment>_car/
(the specialist's own failures fixed by the teacher). Keeps passing layers, rebuilds
(prompt = segment contract + brief, completion = ```js-fenced module), dedups against
the held-out eval briefs (seed 1), and splits ~90/10.

  python pipeline/build_sft.py --segment ground
  -> phase1/ground_sft_train.jsonl, phase1/ground_sft_val.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from segments import SEGMENTS  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True, choices=sorted(SEGMENTS))
    ap.add_argument("--sources", default="train,car", help="tags under data/<segment>_<tag>")
    # fauna: herd_presence passes at p98 >= 1.0, a thin margin; keep only rows whose herd clears it clearly
    ap.add_argument("--min-herd-p98", type=float, default=None,
                    help="keep rows whose herd_presence p98 (2nd-best state) is at least this")
    args = ap.parse_args()
    seg = SEGMENTS[args.segment]
    eval_briefs = {seg["briefs"].brief_text(b) for b in seg["briefs"].sample(24, seed=1)}

    data, per_src, leaks = [], {}, 0
    for tag in args.sources.split(","):
        src = REPO / "phase1" / f"{args.segment}_{tag}"
        if not (src / "log.jsonl").exists():
            continue
        kept = 0
        for line in (src / "log.jsonl").read_text().splitlines():
            r = json.loads(line)
            if not r.get("pass"):
                continue
            if r["brief"] in eval_briefs:
                leaks += 1
                continue
            if args.min_herd_p98 is not None:
                states = r.get("checks", {}).get("herd_presence", {}).get("vs_absent", {})
                p98 = sorted(v["p98"] for v in states.values())
                if len(p98) < 2 or p98[-2] < args.min_herd_p98:
                    continue
            cand = src / (f"cand-{r['id']}-rev.js" if r.get("revised") else f"cand-{r['id']}.js")
            if not cand.exists():
                continue
            data.append({"prompt": seg["prompt"].replace("{brief}", r["brief"]),
                         "completion": "```js\n" + cand.read_text().strip() + "\n```"})
            kept += 1
        per_src[tag] = kept

    random.Random(0).shuffle(data)
    nval = max(6, len(data) // 10)
    val, train = data[:nval], data[nval:]
    out = REPO / "phase1"
    (out / f"{args.segment}_sft_train.jsonl").write_text("".join(json.dumps(d) + "\n" for d in train))
    (out / f"{args.segment}_sft_val.jsonl").write_text("".join(json.dumps(d) + "\n" for d in val))
    # these two .jsonl paths are rewritten by every build, so the set that trained a given adapter is otherwise
    # unrecoverable without notes; the sidecar records exactly how to rebuild it (the raw runs are kept)
    (out / f"{args.segment}_sft.meta.json").write_text(json.dumps({
        "segment": args.segment, "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": args.sources, "kept_per_source": per_src, "min_herd_p98": args.min_herd_p98,
        "eval_collisions_skipped": leaks, "train_rows": len(train), "val_rows": len(val),
        "shuffle_seed": 0, "eval_briefs": "seed 1, n 24",
        "rebuild": (f"python pipeline/build_sft.py --segment {args.segment} --sources {args.sources}"
                    + (f" --min-herd-p98 {args.min_herd_p98}" if args.min_herd_p98 is not None else "")),
    }, indent=2))
    print(f"{args.segment}: sources {per_src}, skipped {leaks} eval collisions -> train {len(train)} / val {len(val)}")


if __name__ == "__main__":
    main()
