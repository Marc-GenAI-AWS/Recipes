"""Make a PEFT LoRA trained on a qwen3_5 base (loaded text-only as Qwen3_5ForCausalLM) servable by vLLM.

vLLM serves Qwen3.5/3.8 checkpoints as Qwen3_5ForConditionalGeneration, whose weight mapper only rewrites
`model.language_model.` -> `language_model.model.`. PEFT saves the text-only keys as `base_model.model.model.layers.N...`,
which that mapper leaves as `model.layers.N...` — no vLLM module has that name, and vLLM validates only the leaf name
(e.g. `in_proj_qkv`), so the adapter loads without error and is silently never applied.

Rewrites `base_model.model.model.layers.` -> `base_model.model.model.language_model.layers.` into a new adapter dir.

  python scripts/remap_lora_keys.py adapters/adapter-fauna-27b-vis adapters/adapter-fauna-27b-vis-vl
"""
import shutil
import sys
from pathlib import Path

from safetensors.torch import load_file, save_file

OLD, NEW = "base_model.model.model.layers.", "base_model.model.model.language_model.layers."

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
if dst.exists():
    sys.exit(f"{dst} already exists")
tensors = load_file(str(src / "adapter_model.safetensors"))
bad = [k for k in tensors if not k.startswith(OLD)]
if bad:
    sys.exit(f"unexpected key prefixes (not remapped): {bad[:5]}")
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("adapter_model.safetensors"))
save_file({NEW + k[len(OLD):]: v for k, v in tensors.items()}, str(dst / "adapter_model.safetensors"))
print(f"remapped {len(tensors)} tensors -> {dst}")
