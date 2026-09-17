"""Local LoRA SFT of Qwen3-4B on the Opus-5 teacher completions, before GRPO.

Why: train_local.py starts GRPO from BASE Qwen3-4B, whose rollouts run clean
only ~18% of the time (reward_log.jsonl). Group-relative advantages carry
almost no signal at that rate. SFT on the 42 harness-verified teacher apps
(data/<segment>_sft_train.jsonl) teaches the layer contract
first; GRPO then starts from a model that mostly works.

  .venv/bin/python sft_local.py                       # Qwen3-4B, 3 epochs, r=32 LoRA
  .venv/bin/python sft_local.py --model Qwen/Qwen3-8B --out adapter-sft-8b

Writes adapters/adapter-sft. Then:
  .venv/bin/python generate_batch.py --fun --adapter adapter-sft --prefix sft4b
  .venv/bin/python generate_batch.py --val --adapter adapter-sft --prefix sft4b-val

Memory: 4B bf16 + LoRA + grad checkpointing at ~8k tokens/sample is well
under 40 GB; a callback still stops the run if MemAvailable drops below
MIN_AVAIL_GB so we never re-create the 2026-08-23 OOM / driver leak.
"""

import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
DATA = REPO / "data"
DEFAULT_MODEL = "Qwen/Qwen3-4B"
# GB10 defaults; on a dedicated SageMaker GPU set GPU_MEM_FRACTION≈0.9, MIN_AVAIL_GB≈4
MIN_AVAIL_GB = float(os.environ.get("MIN_AVAIL_GB", 25))
GPU_MEM_FRACTION = float(os.environ.get("GPU_MEM_FRACTION", 0.6))


def mem_available_gb() -> float:
    """Effective free memory for GPU work on the GB10.

    The nvidia driver keeps freed GPU pages in a pool that later CUDA
    allocations reuse, but the kernel does not count that pool in
    MemAvailable (verified 2026-08-25: 70 GiB allocated on GPU with
    MemAvailable unchanged). So: MemAvailable + driver pool - what this
    process itself currently holds on the GPU.
    """
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":")
        m[k] = int(v.split()[0])
    accounted = sum(m.get(k, 0) for k in ("MemFree", "Buffers", "Cached", "AnonPages",
                                           "Slab", "PageTables", "VmallocUsed", "KernelStack"))
    pool_gb = max(0, m["MemTotal"] - accounted) / 1_048_576
    mine_gb = 0.0
    try:
        import torch
        if torch.cuda.is_initialized():
            mine_gb = torch.cuda.memory_reserved() / 2**30
    except Exception:  # noqa: BLE001
        pass
    return m["MemAvailable"] / 1_048_576 + max(0.0, pool_gb - mine_gb)


def load_rows(path: Path, tok):
    """prompt/completion pairs with the chat template pre-applied (thinking off),
    matching exactly what generate_batch.py / train_local.py feed the model."""
    rows = []
    for line in path.read_text().splitlines():
        r = json.loads(line)
        prompt = tok.apply_chat_template(
            [{"role": "user", "content": r["prompt"]}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        rows.append({"prompt": prompt, "completion": r["completion"] + tok.eos_token})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-length", type=int, default=16_384)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--out", default="adapter-sft")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--data", default=None,
                    help="training jsonl (prompt/completion); default sft_train.jsonl. "
                         "e.g. car/round1/train.jsonl for critique-and-revise data")
    ap.add_argument("--eval-data", default=None, help="eval jsonl; default sft_val.jsonl")
    ap.add_argument("--init-adapter", default=None, help="continue from an existing LoRA dir under adapters/")
    args = ap.parse_args()
    MODEL_ID = args.model

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback
    from trl import SFTConfig, SFTTrainer

    torch.cuda.set_per_process_memory_fraction(GPU_MEM_FRACTION)
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    train = Dataset.from_list(load_rows(Path(args.data) if args.data else DATA / "sft_train.jsonl", tok))
    val = Dataset.from_list(load_rows(Path(args.eval_data) if args.eval_data else DATA / "sft_val.jsonl", tok))
    lens = [len(tok(r["prompt"] + r["completion"])["input_ids"]) for r in train]
    print(f"train {len(train)} / val {len(val)} | tokens per sample "
          f"min {min(lens)} median {sorted(lens)[len(lens) // 2]} max {max(lens)} "
          f"(max_length {args.max_length}: {sum(l > args.max_length for l in lens)} truncated)")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    if args.init_adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(HERE / args.init_adapter), is_trainable=True)
        print(f"continuing from adapters/{args.init_adapter}")

    class MemGuard(TrainerCallback):
        def on_step_end(self, a, state, control, **kw):
            avail = mem_available_gb()
            if avail < MIN_AVAIL_GB:
                print(f"\nMemGuard: {avail:.1f} GB available < {MIN_AVAIL_GB} — saving and stopping")
                control.should_save = True
                control.should_training_stop = True
            return control

    config = SFTConfig(
        output_dir=str(HERE / "checkpoints-sft"),
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=3,                 # ~11 optimizer steps/epoch at 42 samples / accum 4
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        max_length=args.max_length,
        packing=False,
        completion_only_loss=True,      # loss on the app, not the prompt
        bf16=True,
        gradient_checkpointing=True,
        logging_steps=1,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        report_to=[],
    )
    lora = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05,
                      task_type="CAUSAL_LM", target_modules="all-linear")

    trainer = SFTTrainer(model=model, args=config, train_dataset=train,
                         eval_dataset=val, processing_class=tok,
                         peft_config=None if args.init_adapter else lora,
                         callbacks=[MemGuard()])
    trainer.train()
    trainer.save_model(str(HERE / args.out))
    print(f"done -> adapters/{args.out}")


if __name__ == "__main__":
    main()
