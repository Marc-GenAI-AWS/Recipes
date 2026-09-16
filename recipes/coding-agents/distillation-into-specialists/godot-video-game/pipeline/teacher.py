"""Teacher generation: a strong model writes candidate layers from contract + brief.

    python3 pipeline/teacher.py --briefs runs/sky1/briefs.jsonl --out runs/sky1 --k 2
    python3 pipeline/teacher.py --revise runs/sky1/verified.jsonl --out runs/sky1   # fails -> revisions

Writes candidates/<brief>_<k>.gd and candidates.jsonl with the prompt that
produced each one (the same prompt format the specialist is trained on).
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import PIPE, TEACHER_MODEL, converse, extract_code, read, read_jsonl, write_jsonl


def contract_for(segment: str) -> str:
    return read(PIPE / "contract" / f"{segment}.md")


def user_prompt(brief: dict) -> str:
    b = {k: v for k, v in brief.items() if k not in ("id", "contract")}
    return ("Brief (JSON):\n" + json.dumps(b, indent=2) +
            "\n\nWrite the complete layer file for this brief.")


# Street props files run long (the shipped one is ~150 lines of batched geometry):
# 6000 and 9000 token caps cut replies off mid-file and the extractor saved them empty.
TEACHER_MAX_TOKENS = 16000
# props5 (Sep 15): 2 of 96 street briefs x 2 still stopped at 16000, one mid-file at 147 lines
STREET_PROPS_MAX_TOKENS = 32000


def max_tokens_for(brief: dict) -> int:
    if brief["segment"] == "props" and brief.get("world") == "street":
        return STREET_PROPS_MAX_TOKENS
    return TEACHER_MAX_TOKENS


def warn_if_capped(cid: str, usage: dict, cap: int):
    if usage.get("outputTokens", 0) >= cap - 10:
        print(f"  {cid}: hit the {cap}-token output cap, likely truncated", flush=True)


def revise_prompt(brief: dict, previous: str, evidence: str) -> str:
    return (user_prompt(brief) +
            "\n\nYour previous attempt is below. The verifier's evidence follows it. "
            "Fix the problems it names and keep everything that worked. Reply with the full revised file.\n\n"
            "```gdscript\n" + previous + "```\n\nVerifier evidence:\n" + evidence)


def generate(brief, k, out_dir, model, temperature):
    system = contract_for(brief["segment"])
    rows = []
    for i in range(k):
        prompt = user_prompt(brief)
        cap = max_tokens_for(brief)
        text, usage = converse(model, system, [{"text": prompt}], max_tokens=cap, temperature=temperature)
        code = extract_code(text)
        cid = f"{brief['id']}_{i}"
        warn_if_capped(cid, usage, cap)
        (out_dir / "candidates" / f"{cid}.gd").write_text(code)
        rows.append({"candidate": cid, "brief_id": brief["id"], "brief": brief, "segment": brief["segment"],
                     "mode": "write", "prompt": prompt, "teacher": model, "usage": usage,
                     "path": str(out_dir / "candidates" / f"{cid}.gd")})
        print(f"  {cid}: {usage.get('outputTokens', '?')} tokens")
    return rows


def revise(row, out_dir, model, temperature):
    brief = row["brief"]
    system = contract_for(brief["segment"])
    previous = read(row["path"])
    evidence = row.get("evidence", "")
    prompt = revise_prompt(brief, previous, evidence)
    cap = max_tokens_for(brief)
    text, usage = converse(model, system, [{"text": prompt}], max_tokens=cap, temperature=temperature)
    code = extract_code(text)
    cid = row["candidate"] + "r"
    warn_if_capped(cid, usage, cap)
    (out_dir / "candidates" / f"{cid}.gd").write_text(code)
    print(f"  {cid}: revised ({usage.get('outputTokens', '?')} tokens)")
    return {"candidate": cid, "brief_id": brief["id"], "brief": brief, "segment": brief["segment"],
            "mode": "revise", "prompt": prompt, "teacher": model, "usage": usage,
            "parent": row["candidate"], "path": str(out_dir / "candidates" / f"{cid}.gd")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefs")
    ap.add_argument("--revise", help="verified.jsonl; failed rows get one revision each")
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--model", default=TEACHER_MODEL)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out_dir = Path(a.out)
    (out_dir / "candidates").mkdir(parents=True, exist_ok=True)
    rows = []
    with ThreadPoolExecutor(a.workers) as ex:
        if a.briefs:
            briefs = read_jsonl(a.briefs)
            for r in ex.map(lambda b: generate(b, a.k, out_dir, a.model, a.temperature), briefs):
                rows += r
            write_jsonl(out_dir / "candidates.jsonl", rows)
        elif a.revise:
            fails = [r for r in read_jsonl(a.revise) if not r.get("pass")]
            rows = []
            prev = out_dir / "revisions.jsonl"
            if prev.exists() and prev.stat().st_mtime > Path(a.revise).stat().st_mtime:
                # resume: keep revisions written after this verified pass (a checkpoint
                # from an interrupted run); older files belong to an earlier pass
                wanted = {f["candidate"]: f for f in fails}
                rows = [r for r in read_jsonl(prev) if r.get("parent") in wanted and Path(r["path"]).exists()]
                done = {r["parent"] for r in rows}
                fails = [f for f in fails if f["candidate"] not in done]
                print(f"resume: {len(rows)} revisions kept, {len(fails)} to write")
            for r in ex.map(lambda r: revise(r, out_dir, a.model, a.temperature), fails):
                rows.append(r)
                if len(rows) % 10 == 0:
                    write_jsonl(out_dir / "revisions.jsonl", rows)   # checkpoint
            write_jsonl(out_dir / "revisions.jsonl", rows)
    print(f"{len(rows)} candidates -> {out_dir}")


if __name__ == "__main__":
    main()
