"""LoRA SFT for the brief-judge: a vision-language model that scores rendered frames against a brief.

Same recipe as sft_local.py, but multimodal — rows carry `images` alongside prompt/completion message lists, so TRL uses
its vision collator and the model's AutoProcessor instead of a bare tokenizer. Constraints TRL imposes on vision datasets
(and why the config differs from the text trainer): no packing, no padding-free, no assistant-only loss masking.

  .venv/bin/python sft_judge_local.py --model Qwen/Qwen3.5-4B --data ../data/judge_data/rows.jsonl --out adapter-judge
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
GPU_MEM_FRACTION = float(os.environ.get("GPU_MEM_FRACTION", 0.9))

DEFAULT_MODEL = "Qwen/Qwen3.5-4B"


def load_rows(path: Path, limit: int | None = None) -> list[dict]:
    """jsonl rows from collect_judge_data.py -> TRL vision SFT records (images as PIL, resolved from repo-relative paths)."""
    from PIL import Image
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        imgs = []
        for rel in r["images"]:
            p = REPO / rel
            if not p.exists():
                break
            imgs.append(Image.open(p).convert("RGB"))
        if len(imgs) != len(r["images"]):      # a frame went missing: drop the row rather than train on a short prompt
            continue
        out.append({"images": imgs, "prompt": r["prompt"], "completion": r["completion"]})
        if limit and len(out) >= limit:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--data", required=True, help="rows.jsonl from collect_judge_data.py")
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--out", default="adapter-judge")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--max-length", type=int, default=8192)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForImageTextToText, AutoProcessor
    from trl import SFTConfig, SFTTrainer

    torch.cuda.set_per_process_memory_fraction(GPU_MEM_FRACTION)
    rows = load_rows(Path(args.data), args.limit)
    if not rows:
        raise SystemExit(f"no usable rows in {args.data}")
    nval = max(4, int(len(rows) * args.val_frac))
    train_rows, val_rows = rows[nval:], rows[:nval]
    print(f"judge rows: train {len(train_rows)} / val {len(val_rows)} | {len(rows[0]['images'])} frames per row")

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(args.model, dtype=torch.bfloat16, device_map="cuda")

    config = SFTConfig(
        output_dir=str(HERE / "checkpoints-judge"),
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=3,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        max_length=args.max_length,
        packing=False,            # TRL: unsupported for vision datasets
        padding_free=False,       # TRL: unsupported for vision datasets
        bf16=True,
        gradient_checkpointing=True,
        logging_steps=1,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        report_to=[],
    )
    # vision towers are frozen: only the language-side projections are adapted, which is where the scoring behaviour lives
    lora = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules="all-linear", modules_to_save=None)

    trainer = SFTTrainer(model=model, args=config,
                         train_dataset=Dataset.from_list(train_rows),
                         eval_dataset=Dataset.from_list(val_rows),
                         processing_class=processor, peft_config=lora)
    trainer.train()
    trainer.save_model(str(HERE / args.out))
    print(f"done -> adapters/{args.out}")


if __name__ == "__main__":
    main()
