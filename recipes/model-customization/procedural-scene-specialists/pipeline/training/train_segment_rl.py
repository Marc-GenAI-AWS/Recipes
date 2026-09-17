"""GRPO (RLVR) for ANY segment: the layer-harness is the RL environment.

Generalizes train_sky_rl.py (kept for sky reproducibility) via the segment registry.
Each rollout is one layer module; the reward assembles it into the FROZEN host (every
other layer fixed), renders headless, and scores it with the same layer-harness that
filtered the data and accepts the loop's output.

  # local GB10
  .venv/bin/python train_segment_rl.py --segment ground --init-adapter adapter-ground-8b-car
  # SageMaker (paths absolute; GPU_MEM_FRACTION / MIN_AVAIL_GB via env)
  python pipeline/training/train_segment_rl.py --segment ground --init-adapter /opt/ml/input/data/adapter --out /opt/ml/model

Reward: gate_score (hard `runs` gate inside); gate 1.0 but a segment check fails -> 0.85;
no ```js / missing class -> 0.0.
"""

import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "pipeline" / "harness"))
sys.path.insert(0, str(REPO / "scenes"))
sys.path.insert(0, str(REPO / "scenes" / "phase1"))

os.environ.setdefault("HARNESS_THREE_LOCAL", str(REPO / "vendor" / "three.module.min.js"))
os.environ.setdefault("HARNESS_THREE_ADDONS", str(REPO / "vendor" / "three-addons"))
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from harness import render_and_gate, GateResult  # noqa: E402
from layer_harness import assemble, CHECKS, render_robust  # noqa: E402
from gen_sky_baseline import FENCE  # noqa: E402
from segments import SEGMENTS  # noqa: E402
from train_local import mem_available_gb  # noqa: E402

RENDER_WORKERS = int(os.environ.get("RENDER_WORKERS", 2))
MIN_AVAIL_GB = float(os.environ.get("MIN_AVAIL_GB", 30))
GPU_MEM_FRACTION = float(os.environ.get("GPU_MEM_FRACTION", 0.6))
CHECK_PENALTY = 0.85
SEG: dict = {}


def score_layer(completion: str, scratch: Path) -> dict:
    m = FENCE.search(completion)
    js = m.group(1).strip() if m else completion.strip()
    if f"class {SEG['class_name']}" not in js:
        return {"reward": 0.0, "gate": 0.0, "notes": [f"no class {SEG['class_name']} / no js fence"]}
    tag = uuid.uuid4().hex[:10]
    cand, html = scratch / f"c-{tag}.js", scratch / f"b-{tag}.cdn.html"
    try:
        cand.write_text(js)
        assemble(SEG["scene"], SEG["layer"], str(cand), str(html))
        res = render_robust(html.read_text())
    except Exception as e:  # noqa: BLE001 — a hung page / assemble error is a failed rollout, not a failed run
        res = GateResult(); res.notes.append(f"harness error: {str(e)[:120]}")
    finally:
        for p in (cand, html):
            try:
                p.unlink()
            except OSError:
                pass
    gate = res.gate_score()
    out = {"gate": gate, "reward": gate, "notes": res.notes[:2]}
    if gate == 1.0:
        checks = {name: CHECKS[name](res.screenshots)[0] for name in SEG["checks"]}
        out["checks"] = checks
        if not all(checks.values()):
            out["reward"] = CHECK_PENALTY
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", required=True, choices=sorted(SEGMENTS))
    ap.add_argument("--num-prompts", type=int, default=32)
    ap.add_argument("--rollouts", type=int, default=6)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--max-new", type=int, default=4_000)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top-p", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--micro-batch", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--brief-seed", type=int, default=4, help="fresh RL briefs (eval is seed 1)")
    ap.add_argument("--init-adapter", required=True, help="LoRA dir under adapters-rl/ or an absolute path")
    ap.add_argument("--out", default=None, help="default adapter-<segment>-8b-rl; absolute path allowed")
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--resume", default=None)
    args = ap.parse_args()
    SEG.update(SEGMENTS[args.segment])
    out_dir = HERE / (args.out or f"adapter-{args.segment}-8b-rl")   # absolute --out wins in pathlib
    scratch = HERE / f"rl_scratch_{args.segment}"
    scratch.mkdir(exist_ok=True)
    reward_log = (HERE / f"reward_log_{args.segment}.jsonl").open("a")

    import torch
    from datasets import Dataset
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback
    from trl import GRPOConfig, GRPOTrainer

    torch.cuda.set_per_process_memory_fraction(GPU_MEM_FRACTION)
    tok = AutoTokenizer.from_pretrained(args.model)

    def reward_fn(completions, prompts=None, **kwargs):
        t0 = time.time()
        prompts = prompts or [""] * len(completions)
        with ThreadPoolExecutor(RENDER_WORKERS) as ex:
            scored = list(ex.map(lambda c: score_layer(c, scratch), completions))
        for s in scored:
            s["t"] = round(time.time() - t0, 1)
            reward_log.write(json.dumps(s) + "\n")
        reward_log.flush()
        rewards = [s["reward"] for s in scored]
        groups: dict[str, list[int]] = {}
        for i, p in enumerate(prompts):
            groups.setdefault(p, []).append(i)
        var = sum(1 for idxs in groups.values() if len({round(rewards[i], 3) for i in idxs}) > 1)
        print(f"  rewards: {['%.2f' % r for r in rewards]} groups-with-variance: {var}/{len(groups)} "
              f"(render {time.time()-t0:.0f}s)", flush=True)
        return rewards

    briefs = SEG["briefs"]
    eval_briefs = {briefs.brief_text(b) for b in briefs.sample(24, seed=1)}
    prompts = []
    for b in briefs.sample(args.num_prompts + 8, seed=args.brief_seed):
        bt = briefs.brief_text(b)
        if bt in eval_briefs:
            continue
        prompts.append({"prompt": tok.apply_chat_template(
            [{"role": "user", "content": SEG["prompt"].replace("{brief}", bt)}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)})
        if len(prompts) >= args.num_prompts:
            break
    dataset = Dataset.from_list(prompts)
    print(f"{args.segment} RL: {len(dataset)} prompts x {args.rollouts} rollouts from {args.init_adapter} "
          f"-> {out_dir}", flush=True)

    config = GRPOConfig(
        output_dir=str(HERE / f"checkpoints-{args.segment}-rl"),
        num_train_epochs=args.epochs, num_generations=args.rollouts,
        per_device_train_batch_size=args.micro_batch,
        gradient_accumulation_steps=args.rollouts // args.micro_batch,
        max_completion_length=args.max_new, learning_rate=args.lr,
        bf16=True, gradient_checkpointing=True, logging_steps=1,
        save_strategy="steps", save_steps=4, save_total_limit=3, report_to=[],
        temperature=args.temperature, top_p=args.top_p, top_k=args.top_k,
        mask_truncated_completions=True,
        model_init_kwargs={"dtype": torch.bfloat16, "device_map": "cuda"},
    )

    class MemGuard(TrainerCallback):
        def on_step_end(self, a, state, control, **kw):
            avail = mem_available_gb()
            if avail < MIN_AVAIL_GB:
                print(f"\nMemGuard: {avail:.1f} GB available < {MIN_AVAIL_GB} — saving and stopping", flush=True)
                control.should_save = True
                control.should_training_stop = True
            return control

    base = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16, device_map="cuda")
    model = PeftModel.from_pretrained(base, str(HERE / args.init_adapter), is_trainable=True)
    trainer = GRPOTrainer(model=model, reward_funcs=reward_fn, args=config,
                          train_dataset=dataset, peft_config=None, callbacks=[MemGuard()])
    _gen = trainer._generate_single_turn

    def _gen_eval(*a, **kw):   # eval mode keeps Qwen3's KV cache under grad checkpointing
        trainer.model.eval()
        try:
            return _gen(*a, **kw)
        finally:
            trainer.model.train()
    trainer._generate_single_turn = _gen_eval

    trainer.train(resume_from_checkpoint=args.resume or None)
    trainer.save_model(str(out_dir))
    print(f"done -> {out_dir}", flush=True)


if __name__ == "__main__":
    main()
