"""Phase 1 baseline C — the teacher (Bedrock Claude Fable 5.1) ceiling for the
SKY layer, verified through the layer-harness in the frozen High Park host.

For each held-out sky brief: Fable writes an `Atmosphere` sky-dome layer against
the frozen contract; the layer-harness drops it into High Park (all other layers
fixed), runs the render gates, and adds the greycard (exposure) + horizon
(framing) checks. Emits a per-brief log + a summary distribution.

  python scenes/phase1/gen_sky_baseline.py --n 24 --workers 2 --tag fable
  VISUAL_MODEL=us.anthropic.claude-opus-5 python scenes/phase1/gen_sky_baseline.py --n 8   # fallback model

Env: AWS creds for Bedrock (region us-west-2; Fable needs data-retention aws_review).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.config import Config

HERE = Path(__file__).resolve().parent
SCENES = HERE.parent
REPO = SCENES.parent
sys.path.insert(0, str(SCENES))
sys.path.insert(0, str(HERE))

from sky_briefs import sample, brief_text  # noqa: E402
from layer_harness import assemble, CHECKS, render_and_gate  # noqa: E402

MODEL = os.environ.get("VISUAL_MODEL", "us.anthropic.claude-fable-5-1")
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"
PRICE = {"fable": (10.0, 50.0), "opus": (5.0, 25.0)}  # $/MTok in, out
BEDROCK_CFG = Config(read_timeout=600, connect_timeout=30, retries={"max_attempts": 3, "mode": "adaptive"})
FENCE = re.compile(r"```(?:js|javascript)?\s*\n(.*?)```", re.S)

SCENE = "highpark"
LAYER = "layers/atmosphere.js"

PROMPT = """You are a senior Three.js graphics engineer. Write ONE layer of a modular,
single-file real-time scene ("High Park", a mountain-prairie basin under peaks):
the SKY DOME. Output a single ES module that exports `class Atmosphere` and nothing else.

The module is assembled into a FROZEN host scene — you may only build the sky. Contract:

  export class Atmosphere {
    constructor(ctx) {
      // ctx = { THREE, scene, camera, renderer, U, rnd, rr, cur }
      // Add exactly ONE sky-dome mesh to ctx.scene: a BackSide SphereGeometry (radius ~1200),
      // depthWrite:false, ShaderMaterial with uniforms = uniformsFor(ctx.U, { ...optional extras }).
      // The vertex shader should pass a normalized view/world direction to the fragment.
    }
    // add update(dt, t) only if you animate your own extra uniforms; U.uTime already advances.
  }

In scope (no import needed; importing from '../../contract/runtime.js' or '../prelude.glsl.js'
is also fine — imports are stripped at assembly):
  - uniformsFor(U, extra)  -> your material's uniforms MUST be built with this (shares the palette).
  - G     -> a GLSL prelude string; PREPEND it to your fragmentShader. It declares the uniforms
             below and provides: hash1(vec3), noise3(vec3), fbm3(vec3), fbm2(vec2), and FLASH_C (vec3).
  - TAIL  -> APPEND it to your fragmentShader; it closes main() with tonemapping + colorspace.

Uniforms G declares (read what you need): uTime float; uSkyTop vec3, uSkyHorizon vec3 (zenith &
horizon palette, per state); uSunC vec3, uSunI float, uSunDir vec3; uFogC vec3 (haze colour);
uCloud float (0..1 coverage); uShaft float (hero-light strength); uFlash float (lightning);
uSaddle vec3 (the gap the sun sits over). G ALSO declares: uFogD float, uShadowAmt float,
uWind float, uShaftDir vec3.
CRITICAL: every uniform listed above is ALREADY DECLARED by G (which you prepend). Do NOT
re-declare any of them in your shader — a duplicate line like `uniform float uWind;` is a GLSL
"redefinition" compile error and WILL fail the harness. The ONLY uniform you may declare yourself
is `uniform float uStars;` (0..1), plus any brand-new uniforms of your own invention.

The four host states drive these every frame; your sky must read well across ALL of them:
dawn "first-light", bright windy "cloud-shadows", dark "storm-break", "gold-dusk".
The per-state COLORS come from the uniforms — your job is the cloud/sun/atmosphere TECHNIQUE.

Rules: procedural only, no external assets/textures; one dome mesh; the fragment's LAST statement
must be `gl_FragColor = vec4(col, 1.0);` followed by TAIL. TAIL only tonemaps gl_FragColor and closes
main() — if you never write gl_FragColor the dome renders BLACK. (The dome is the backdrop, do NOT
call fog().) Keep it <= ~120 lines; runs clean in three.js r169.

BRIEF: {brief}

Output ONLY a single ```js fenced ES module. Nothing before or after the fence."""

REPAIR_PROMPT = """Your High Park sky layer failed the render harness. Fix it with the SMALLEST change
that resolves the observation while keeping the visual intent. The most common cause is
re-declaring a uniform that the shared prelude G already declares (e.g. a duplicate
`uniform float uWind;`) — delete the duplicate declaration if so. Another is a GLSL type or
syntax slip. A dome that renders BLACK means gl_FragColor is never written — the fragment must end
with `gl_FragColor = vec4(col, 1.0);` + TAIL. Keep it ONE dome mesh, uniforms via uniformsFor(ctx.U, ...).

HARNESS OBSERVATION:
{notes}

YOUR MODULE:
```js
{js}
```

Output ONLY the corrected ES module in a single ```js fence. Nothing else."""


# generator: "fable" (Bedrock) or "r4"/any (OpenAI-compatible endpoint, e.g. sm_proxy on :4000)
GENERATOR = "fable"
ENDPOINT = "http://127.0.0.1:4000/v1"
GEN_MODEL = "qwen3-r4"
# reviser for the critique-and-revise pass on failures; default = same as generator.
# Set REVISER="fable" to have the TEACHER fix the student's failures (the proven CaR recipe).
REVISER = None  # resolved to GENERATOR in main() unless overridden


def price(usage: dict) -> float:
    if GENERATOR != "fable":
        return 0.0  # self-hosted SageMaker endpoint: no per-token charge here
    pin, pout = PRICE["fable"] if "fable" in MODEL else PRICE["opus"]
    return (usage.get("inputTokens", 0) * pin + usage.get("outputTokens", 0) * pout) / 1e6


def _converse_bedrock(text: str, max_tokens: int) -> tuple[str, dict]:
    client = boto3.client("bedrock-runtime", region_name=REGION, config=BEDROCK_CFG)
    resp = client.converse(modelId=MODEL, messages=[{"role": "user", "content": [{"text": text}]}],
                           inferenceConfig={"maxTokens": max_tokens})
    out = "\n".join(b["text"] for b in resp["output"]["message"]["content"] if "text" in b)
    return out, resp.get("usage", {})


def _openai_endpoint(text: str, max_tokens: int) -> tuple[str, dict]:
    body = json.dumps({"model": GEN_MODEL, "messages": [{"role": "user", "content": text}],
                       "max_tokens": max_tokens, "temperature": 0.7, "top_p": 0.8,
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()  # Qwen3: no <think> budget burn
    req = urllib.request.Request(ENDPOINT.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    out = d["choices"][0]["message"]["content"]
    u = d.get("usage", {})
    return out, {"inputTokens": u.get("prompt_tokens", 0), "outputTokens": u.get("completion_tokens", 0)}


def converse(text: str, max_tokens: int = 8000) -> tuple[str, dict]:
    return _converse_bedrock(text, max_tokens) if GENERATOR == "fable" else _openai_endpoint(text, max_tokens)


def revise(text: str, max_tokens: int = 8000) -> tuple[str, dict]:
    """The critique-and-revise call — may use a different model than the generator."""
    return _converse_bedrock(text, max_tokens) if REVISER == "fable" else _openai_endpoint(text, max_tokens)


def revise_cost(usage: dict) -> float:
    if REVISER != "fable":
        return 0.0
    return (usage.get("inputTokens", 0) * 10.0 + usage.get("outputTokens", 0) * 50.0) / 1e6


def verify(brief_id: str, candidate_js: str, out: Path) -> dict:
    cand = out / f"cand-{brief_id}.js"
    cand.write_text(candidate_js)
    build = out / f"build-{brief_id}.cdn.html"
    assemble(SCENE, LAYER, str(cand), str(build))
    res = render_and_gate(Path(build).read_text())
    gate = res.gate_score()
    g_ok, g_detail = CHECKS["greycard"](res.screenshots)
    h_ok, h_detail = CHECKS["horizon"](res.screenshots)
    return {"gate": gate, "gates": res.gates, "notes": res.notes[:2],
            "greycard": {"pass": g_ok, **g_detail}, "horizon": {"pass": h_ok, **h_detail},
            "pass": gate == 1.0 and g_ok and h_ok}


def process(brief: dict, out: Path) -> dict:
    t0 = time.time()
    rec = {"id": brief["id"], "brief": brief_text(brief), "cost": 0.0}
    try:
        text, usage = converse(PROMPT.replace("{brief}", brief_text(brief)))
        rec["cost"] = round(price(usage), 4)
        rec["out_tokens"] = usage.get("outputTokens", 0)
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"fable: {str(e)[:160]}"
        return rec
    m = FENCE.search(text)
    js = (m.group(1).strip() if m else text.strip())
    if "class Atmosphere" not in js:
        rec["error"] = "no `class Atmosphere` in output"
        rec["raw"] = text[:400]
        return rec
    try:
        v = verify(brief["id"], js, out)
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"verify: {str(e)[:200]}"
        rec["seconds"] = round(time.time() - t0)
        return rec
    rec.update(v); rec["attempts"] = 1
    if not v["pass"]:
        # one critique-and-revise pass: feed the harness note back to the teacher
        try:
            notes = "\n".join(f"- {n}" for n in (v["notes"] or ["(no notes)"]))
            rtext, rusage = revise(REPAIR_PROMPT.replace("{notes}", notes).replace("{js}", js))
            rec["cost"] = round(rec["cost"] + revise_cost(rusage), 4)
            rm = FENCE.search(rtext)
            js2 = (rm.group(1).strip() if rm else rtext.strip())
            if "class Atmosphere" in js2:
                v2 = verify(brief["id"] + "-rev", js2, out)
                rec["attempts"] = 2; rec["revise_gate"] = v2["gate"]; rec["revise_pass"] = v2["pass"]
                if v2["pass"]:
                    rec.update(v2); rec["revised"] = True
        except Exception as e:  # noqa: BLE001
            rec["revise_error"] = str(e)[:150]
    rec["seconds"] = round(time.time() - t0)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24, help="number of held-out sky briefs")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None, help="cap briefs this run (for a smoke)")
    ap.add_argument("--tag", default="fable")
    ap.add_argument("--generator", default="fable", help="'fable' (Bedrock) or 'r4' (OpenAI endpoint via sm_proxy)")
    ap.add_argument("--endpoint", default="http://127.0.0.1:4000/v1", help="OpenAI-compatible base URL")
    ap.add_argument("--gen-model", default="qwen3-r4", help="model name the proxy routes on")
    ap.add_argument("--reviser", default=None, help="critique-and-revise model: 'fable' (teacher) or default = generator")
    args = ap.parse_args()

    global GENERATOR, ENDPOINT, GEN_MODEL, REVISER
    GENERATOR, ENDPOINT, GEN_MODEL = args.generator, args.endpoint, args.gen_model
    REVISER = args.reviser or args.generator
    print(f"generator={GENERATOR} reviser={REVISER}", flush=True)

    briefs = sample(args.n, args.seed)
    out = REPO / "phase1" / f"sky_baseline_{args.tag}"
    out.mkdir(parents=True, exist_ok=True)
    log = out / "log.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    todo = [b for b in briefs if b["id"] not in done][: args.limit]
    print(f"sky baseline [{args.tag}] model={MODEL} region={REGION}: {len(briefs)} briefs, {len(done)} done, {len(todo)} to do", flush=True)

    passed, cost = 0, 0.0
    with log.open("a") as f, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process, b, out): b for b in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            f.write(json.dumps(rec) + "\n"); f.flush()
            passed += 1 if rec.get("pass") else 0
            cost += rec.get("cost", 0.0)
            if rec.get("error"):
                status = f"ERR {rec['error'][:70]}"
            else:
                gc = rec.get("greycard", {}); status = (f"gate {rec['gate']} grey={'ok' if gc.get('pass') else 'X'} "
                          f"horizon={'ok' if rec.get('horizon', {}).get('pass') else 'X'} {'PASS' if rec.get('pass') else 'fail'}")
            print(f"  [{n}/{len(todo)}] {rec['id']} {status} ${rec.get('cost', 0):.3f} ({rec.get('seconds', '?')}s) | pass {passed} ${cost:.2f}", flush=True)

    # summary over the whole log
    rows = [json.loads(l) for l in log.read_text().splitlines()]
    ok = [r for r in rows if r.get("pass")]
    gate1 = [r for r in rows if r.get("gate") == 1.0]
    lumas = [v for r in ok for v in (r.get("greycard", {}).get("mean_luma") or {}).values()]
    summary = {
        "model": MODEL, "briefs": len(rows),
        "gate_1.0": len(gate1), "pass_all_checks": len(ok),
        "pass_rate": round(len(ok) / max(1, len(rows)), 3),
        "luma_range": [round(min(lumas), 1), round(max(lumas), 1)] if lumas else None,
        "total_cost": round(sum(r.get("cost", 0.0) for r in rows), 2),
        "errors": [r["id"] for r in rows if r.get("error")],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print("SKY-BASELINE-DONE:", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
