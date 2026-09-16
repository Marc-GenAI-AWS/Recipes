"""Token-length audit of an SFT dataset. Run this before every training job.

    python scripts/check_lengths.py runs/sky1/sft/train.jsonl --max-len 14336

Training frameworks truncate silently at their sequence length, and the loss is computed
on whatever survives. On this project a 6,144-token cut-off silently destroyed 528 of 529
examples for one part: every repair example kept the prompt and none of the answer, so the
model was trained to produce nothing. Raising the cut-off lifted that part from 38% to 71%
with no change to the data.

Exits non-zero if any example would lose answer tokens, so it can gate a training script.
"""
import argparse
import json
import sys
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="jsonl with a 'messages' list per row")
    ap.add_argument("--max-len", type=int, required=True, help="the sequence length you will train at")
    ap.add_argument("--tokenizer", default=None, help="model id or path (default: the dataset's base model)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    from transformers import AutoTokenizer
    tok_id = a.tokenizer or "Qwen/Qwen2.5-Coder-3B-Instruct"
    tok = AutoTokenizer.from_pretrained(tok_id)

    rows = [json.loads(l) for l in open(a.dataset)]
    cut, starved, lengths = 0, 0, []
    by_mode = Counter()
    for r in rows:
        msgs = r["messages"]
        prompt = len(tok.apply_chat_template(msgs[:-1], tokenize=True, add_generation_prompt=True))
        full = len(tok.apply_chat_template(msgs, tokenize=True))
        lengths.append(full)
        if full > a.max_len:
            cut += 1
            by_mode[r.get("mode", "?")] += 1
            if prompt >= a.max_len:      # nothing of the answer survives: a wasted example
                starved += 1

    lengths.sort()
    pct = lambda q: lengths[min(len(lengths) - 1, int(q * len(lengths)))]  # noqa: E731
    if not a.quiet:
        print(f"{len(rows)} examples, tokenizer {tok_id}")
        print(f"  length  median {pct(.5)}  p95 {pct(.95)}  max {lengths[-1]}")
        print(f"  at --max-len {a.max_len}: {cut} truncated, {starved} with no answer tokens left")
        if cut:
            print("  truncated by kind:", dict(by_mode))
            print(f"  -> train at >= {lengths[-1]} tokens, or shorten the system prompt")
    if starved:
        print(f"FAIL: {starved} examples would train on no answer at all", file=sys.stderr)
        return 1
    if cut:
        print(f"WARNING: {cut} examples lose the end of their answer", file=sys.stderr)
        return 1
    print("OK: every example fits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
