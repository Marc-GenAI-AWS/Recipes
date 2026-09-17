"""Re-pair verified layers with DERIVED contracts, so the specialists read the contract we actually ship.

The existing corpus was generated against hand-written per-host contracts: each row is

    prompt      = <hand-written highpark contract> + "BRIEF: <one paragraph>"
    completion  = a layer that passed the harness

The completion is the expensive half and it is still valid: it was verified by render, and nothing about the
host changed. Only the prompt is stale. So a new dataset costs a regex and a descriptor call rather than
another generation pass — no GPU, no re-rendering, no re-verification.

What this does NOT do is make the data multi-world. Every row here is still one host; re-prompting unifies the
FORMAT so a specialist reads a derived contract, which is the prerequisite for training across worlds, not the
thing itself.

  python scripts/reprompt_dataset.py --scene highpark
  python scripts/reprompt_dataset.py --scene highpark --example highpark:shafts.js --suffix unified-ex
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from descriptor import contract_text, descriptor  # noqa: E402

# class name per segment, as the frozen host names it
CLASS_NAMES = {"sky": "Atmosphere", "ground": "Prairie", "camera": "CameraRig",
               "vegetation": "Grass", "fauna": "Herd", "effects": "Mist"}

BRIEF = re.compile(r"BRIEF:\s*(.+?)(?:\n\n|\nOutput ONLY)", re.S)


def split_old_prompt(p: str) -> tuple[str, str, str]:
    """Pull out the parts of a hand-written prompt that the derived contract does NOT already say.

    Three of the four sections are now generated — the class contract, the "In scope" API list, and the generic
    Rules — so carrying them over would duplicate and, in places, contradict the derived text. Two are not
    derivable and must survive, or the prompt stops explaining its own completion:

      head : what this layer IS in this world ("the PRAIRIE GROUND - the rolling turf the herd stands on")
      req  : structural requirements other layers depend on (ground's exact PlaneGeometry and groundH sampling,
             fauna's home-meadow radius and animal size). Drop these and SFT teaches the model to emit
             highpark's magic numbers unconditionally - memorising the world instead of learning the contract.
    """
    head = p[:p.find("Output a single ES module")].strip()
    if "): " in head:                      # strip the role framing and scene name, keep the layer description
        head = head.split("): ", 1)[1].strip()
    i = p.find("In scope")
    req = ""
    if i > 0:
        cb = p.rfind("}", 0, i)            # end of the class-contract code block
        req = p[cb + 1:i].strip()
    m = BRIEF.search(p)
    return head, req, (m.group(1).strip() if m else "")


def imports_for(scene: str) -> str:
    """Build the import block from the host's real exports, rather than restating them by hand."""
    h = descriptor(scene)
    lines = ["import * as THREE from 'three';"]
    if h.prelude_exports:
        lines.append(f"import {{ {', '.join(h.prelude_exports)} }} from '../prelude.glsl.js';   // whichever you need")
    lines.append("import { uniformsFor } from '../../contract/runtime.js';")
    if h.js_helpers:
        lines.append(f"// host JS helpers, if useful: {', '.join(h.js_helpers)}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="highpark", help="host these completions were verified against")
    ap.add_argument("--dir", default="phase1", help="where the *_sft_train.jsonl live")
    ap.add_argument("--segments", default="sky,ground,camera,vegetation,fauna,effects")
    ap.add_argument("--example", default="", help="worked layer to embed, as scene:file.js")
    ap.add_argument("--suffix", default="unified", help="output becomes <seg>_sft_<split>.<suffix>.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ex = tuple(args.example.split(":", 1)) if args.example else None
    imports = imports_for(args.scene)
    total_in = total_out = 0

    for seg in [s.strip() for s in args.segments.split(",") if s.strip()]:
        cls = CLASS_NAMES.get(seg)
        if not cls:
            print(f"{seg:12} no class name registered — skipping")
            continue
        for split in ("train", "val"):
            src = REPO / args.dir / f"{seg}_sft_{split}.jsonl"
            if not src.exists():
                continue
            rows = [json.loads(l) for l in src.open() if l.strip()]
            total_in += len(rows)
            out_rows, skipped = [], 0
            for r in rows:
                head, req, brief = split_old_prompt(r["prompt"])
                if not brief:
                    skipped += 1
                    continue
                intent = "\n\n".join(x for x in (head, req, f"BRIEF: {brief}") if x)
                prompt = contract_text(args.scene, cls, intent, imports, ex)
                out_rows.append({"prompt": prompt, "completion": r["completion"]})
            total_out += len(out_rows)
            dst = REPO / args.dir / f"{seg}_sft_{split}.{args.suffix}.jsonl"
            if not args.dry_run:
                with dst.open("w") as f:
                    for row in out_rows:
                        f.write(json.dumps(row) + "\n")
            note = f"  ({skipped} without a BRIEF, dropped)" if skipped else ""
            avg = sum(len(r["prompt"]) for r in out_rows) // max(len(out_rows), 1)
            print(f"{seg:12} {split:5} {len(rows):4} -> {len(out_rows):4} rows   prompt avg {avg:5} chars{note}")

    print(f"\n{total_out}/{total_in} rows re-prompted against the derived {args.scene} contract"
          + (f" with a worked example from {ex[0]}" if ex else ""))
    if args.dry_run:
        print("(dry run — nothing written)")


if __name__ == "__main__":
    main()
