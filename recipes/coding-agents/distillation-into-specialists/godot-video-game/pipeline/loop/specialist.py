"""Specialist inference: one call = one layer file from contract + brief.

Backends (--backend):
  teacher            Claude on Bedrock (the stand-in until a specialist is trained)
  local:<url>        an OpenAI-compatible server, e.g. vLLM on the dev box serving
                     the merged SFT weights: vllm serve <model_dir> --port 8000
  endpoint:<name>    a SageMaker real-time endpoint (DJL/TGI/vLLM container,
                     OpenAI-compatible or "inputs" JSON)

Batch mode (used by the evaluation stage and by hand):
    python3 pipeline/loop/specialist.py --segment sky --briefs heldout_briefs.jsonl --out runs/eval1 \
        --backend local:http://127.0.0.1:8000/v1 --model sky-sft
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import PIPE, TEACHER_MODEL, converse, extract_code, read, read_jsonl, write_jsonl  # noqa: E402
from teacher import revise_prompt, user_prompt  # noqa: E402


class Specialist:
    def __init__(self, segment: str, backend: str = "teacher", model: str = None):
        self.segment = segment
        self.backend = backend
        self.model = model
        self.system = read(PIPE / "contract" / f"{segment}.md")

    def _chat(self, prompt: str) -> str:
        if self.backend == "teacher":
            text, _ = converse(self.model or TEACHER_MODEL, self.system, [{"text": prompt}])
            return text
        if self.backend.startswith("local:"):
            import urllib.request
            url = self.backend[len("local:"):].rstrip("/") + "/chat/completions"
            body = {"model": self.model or "specialist", "max_tokens": 6000, "temperature": 0.4,
                    "messages": [{"role": "system", "content": self.system}, {"role": "user", "content": prompt}]}
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        if self.backend.startswith("hf:"):
            return self._hf_generate([prompt])[0]
        if self.backend.startswith("endpoint:"):
            import boto3
            name = self.backend[len("endpoint:"):]
            rt = boto3.client("sagemaker-runtime")
            body = {"messages": [{"role": "system", "content": self.system}, {"role": "user", "content": prompt}],
                    "max_tokens": 6000, "temperature": 0.4}
            r = rt.invoke_endpoint(EndpointName=name, ContentType="application/json", Body=json.dumps(body))
            out = json.loads(r["Body"].read())
            if "choices" in out:
                return out["choices"][0]["message"]["content"]
            return out.get("generated_text", json.dumps(out))
        raise ValueError("unknown backend " + self.backend)

    # transformers generation on a local GPU (no vLLM needed); batched for eval
    _hf = None

    def _hf_load(self):
        if self._hf is None:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            path = self.backend[len("hf:"):]
            tok = AutoTokenizer.from_pretrained(path)
            tok.padding_side = "left"
            tok.pad_token = tok.pad_token or tok.eos_token
            model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.bfloat16, device_map="cuda")
            model.eval()
            self._hf = (tok, model)
        return self._hf

    # 4096: props layers run long (training answers up to ~3,760 tokens; Qwen splits every digit), and
    # one props1234 eval output stopped at the old 3000 cap
    def _hf_generate(self, prompts: list, max_new_tokens=4096) -> list:
        import torch
        tok, model = self._hf_load()
        texts = [tok.apply_chat_template([{"role": "system", "content": self.system}, {"role": "user", "content": p}],
                                         tokenize=False, add_generation_prompt=True) for p in prompts]
        enc = tok(texts, return_tensors="pt", padding=True).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.4, top_p=0.95,
                                 pad_token_id=tok.pad_token_id)
        return [tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True) for o in out]

    def write_many(self, briefs: list, batch=8) -> list:
        """Batched write for the hf backend; falls back to one call per brief otherwise."""
        if not self.backend.startswith("hf:"):
            return [self.write(b) for b in briefs]
        outs = []
        for i in range(0, len(briefs), batch):
            chunk = briefs[i:i + batch]
            prompts = [user_prompt(b) for b in chunk]
            for text, prompt in zip(self._hf_generate(prompts), prompts):
                outs.append((extract_code(text), prompt))
            print(f"  generated {len(outs)}/{len(briefs)}", flush=True)
        return outs

    def write(self, brief: dict) -> tuple:
        prompt = user_prompt(brief)
        return extract_code(self._chat(prompt)), prompt

    def revise(self, brief: dict, previous: str, evidence: str) -> tuple:
        prompt = revise_prompt(brief, previous, evidence)
        return extract_code(self._chat(prompt)), prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", default="sky")
    ap.add_argument("--briefs")
    ap.add_argument("--revise", help="verified.jsonl: the specialist revises its own fails from the evidence")
    ap.add_argument("--out", required=True)
    ap.add_argument("--backend", default="teacher")
    ap.add_argument("--model")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "candidates").mkdir(parents=True, exist_ok=True)
    sp = Specialist(a.segment, a.backend, a.model)
    rows = []
    if a.revise:
        fails = [r for r in read_jsonl(a.revise) if not r.get("pass")]
        prompts = [revise_prompt(r["brief"], read(r["path"]), r.get("evidence", "")) for r in fails]
        if a.backend.startswith("hf:"):
            texts = []
            for i in range(0, len(prompts), 8):
                texts += sp._hf_generate(prompts[i:i + 8])
                print(f"  revised {len(texts)}/{len(prompts)}", flush=True)
        else:
            texts = [sp._chat(p) for p in prompts]
        for r, prompt, text in zip(fails, prompts, texts):
            cid = r["candidate"] + "r"
            p = out / "candidates" / f"{cid}.gd"
            p.write_text(extract_code(text))
            rows.append({"candidate": cid, "brief_id": r["brief_id"], "brief": r["brief"], "segment": a.segment,
                         "mode": "revise", "prompt": prompt, "path": str(p), "backend": a.backend, "parent": r["candidate"]})
        write_jsonl(out / "revisions.jsonl", rows)
        return
    briefs = read_jsonl(a.briefs)
    for b, (code, prompt) in zip(briefs, sp.write_many(briefs)):
        cid = b["id"] + "_s"
        p = out / "candidates" / f"{cid}.gd"
        p.write_text(code)
        rows.append({"candidate": cid, "brief_id": b["id"], "brief": b, "segment": a.segment, "mode": "write",
                     "prompt": prompt, "path": str(p), "backend": a.backend})
        print(" ", cid, len(code), "chars")
    write_jsonl(out / "candidates.jsonl", rows)


if __name__ == "__main__":
    main()
