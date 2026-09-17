"""Audit a segment's contract against the host it actually codes against — before spending on GPUs.

Checks three things a contract gets wrong in practice:
  1. every GLSL helper signature the contract names matches the host prelude (wrong argument types are silent until a
     shader fails to compile);
  2. every helper the prelude exports is mentioned somewhere (an undocumented helper is one the model will not use, or
     will re-implement badly);
  3. every preprocessor symbol the prelude *uses but does not declare* is called out in the contract — these are the
     preconditions the hand-built reference layer satisfies silently.

Exists because the first run of a new segment scored 0/12 on exactly these: an undocumented required `#define`, and two
helpers documented as taking a vec3 that take a vec2. The model followed the contract it was given.

  python scripts/verify_contract.py ocean
  python scripts/verify_contract.py --all
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import SCENES  # noqa: E402
from pipeline.contract.segments import SEGMENTS  # noqa: E402

SIG = re.compile(r"^\s*(float|int|bool|vec[234]|mat[234])\s+(\w+)\s*\(([^)]*)\)", re.M)
# a symbol used in a preprocessor condition or loop bound that the file never #defines
DEFINE_USE = re.compile(r"(?:#if(?:def)?\s+|<\s*)([A-Z][A-Z0-9_]{2,})")


def prelude_for(scene: str) -> tuple[Path | None, str]:
    for name in ("prelude.glsl.js", "prelude.js"):
        p = SCENES / scene / name
        if p.exists():
            return p, p.read_text()
    return None, ""


def audit(segment: str) -> int:
    seg = SEGMENTS[segment]
    path, src = prelude_for(seg["scene"])
    if not path:
        print(f"{segment}: no prelude found for scene {seg['scene']} — nothing to audit")
        return 0
    prompt = seg["prompt"]
    real = {n: (ret, args.strip()) for ret, n, args in SIG.findall(src)}
    claimed = {n: (ret, args) for ret, n, args in re.findall(r"\b(float|int|bool|vec[234]|mat[234])\s+(\w+)\(([^)]*)\)", prompt)}

    problems = 0
    for name, (ret, args) in claimed.items():
        if name not in real:
            continue
        r_ret, r_args = real[name]
        first, r_first = (args.split() or [""])[0], (r_args.split() or [""])[0]
        if ret != r_ret or first != r_first:
            print(f"  MISMATCH {name}: contract says '{ret} {name}({args})', prelude has '{r_ret} {name}({r_args})'")
            problems += 1

    undocumented = sorted(set(real) - set(claimed))
    if undocumented:
        print(f"  UNDOCUMENTED helpers the prelude exports: {', '.join(undocumented)}")
        problems += len(undocumented)

    declared = set(re.findall(r"#define\s+([A-Z][A-Z0-9_]+)", src))
    required = {s for s in DEFINE_USE.findall(src) if s not in declared and s.isupper()}
    for sym in sorted(required):
        if sym not in prompt:
            print(f"  UNSTATED PRECONDITION: the prelude uses '{sym}' but never declares it — the contract must tell "
                  f"the model to supply it (e.g. via the material's `defines`)")
            problems += 1

    print(f"{segment} ({seg['scene']}): {'OK' if not problems else str(problems) + ' problem(s)'}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("segment", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    targets = sorted(SEGMENTS) if args.all or not args.segment else [args.segment]
    total = sum(audit(s) for s in targets)
    raise SystemExit(1 if total else 0)


if __name__ == "__main__":
    main()
