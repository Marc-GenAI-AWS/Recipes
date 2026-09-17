"""Director planner: scene themes -> one coherent brief per segment.

The specialists were trained on briefs from each segment's sampler, so the planner does not write free-form briefs.
For every theme it samples candidate briefs from each sampler and asks a Bedrock model to PICK the most coherent
combination across segments (e.g. a storm sky with storm-running herds and mist in the hollows). Only the trailing
"Mood: ..." clause may be reworded, keeping the rest of each brief in the specialists' training distribution.

  python pipeline/planner.py --out data/plans/demo.json \
      --theme "a storm breaking over the high prairie as a bison herd bunches and runs" \
      --theme "a hushed misty dawn with elk grazing in the hollows"

Writes {"model", "scenes": [{"id", "theme", "briefs": {segment: text}, "picked": {segment: index}}]}.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import gen_sky_baseline as gsb  # noqa: E402  (boto3 client config, region)
import theme_briefs  # noqa: E402
from segments import SEGMENTS  # noqa: E402

SEGMENT_ORDER = ["sky", "ground", "camera", "vegetation", "fauna", "effects"]
PLANNER_MODEL = "us.anthropic.claude-opus-5"
GENERATOR, ENDPOINT, GEN_MODEL = "opus", "http://localhost:8001/v1", "planner"

PROMPT = """You are the art director for a procedural Three.js landscape: a high mountain prairie with peaks, a meadow basin,
grass, a herd of large animals, drifting mist, and a camera rig. The scene cycles through three lighting states
(first light, cloud shadows, storm break) on its own; each layer must still read well in all of them.

THEME: {theme}

For each segment below you get numbered candidate briefs. Pick exactly ONE candidate per segment so that the six picks
tell one coherent story that fits the theme (sky, mist and grass mood agree; the camera framing suits the herd; the herd's
behaviour suits the weather). Copy the picked brief VERBATIM, except that you may reword its final "Mood: ..." clause
(two or three adjectives) to fit the theme. Do not add, remove or reword any other clause.

{candidates}

Answer with ONLY a JSON object, no prose, no code fence:
{{"sky": {{"index": <n>, "brief": "<text>"}}, "ground": {{...}}, "camera": {{...}}, "vegetation": {{...}}, "fauna": {{...}}, "effects": {{...}}}}"""


def candidates(n: int, seed: int) -> dict[str, list[str]]:
    return {seg: [SEGMENTS[seg]["briefs"].brief_text(b) for b in SEGMENTS[seg]["briefs"].sample(n, seed)]
            for seg in SEGMENT_ORDER}


def strip_mood(text: str) -> str:
    return re.sub(r"\s*Mood:[^.]*\.?\s*$", "", text.strip())


def ask(prompt: str) -> tuple[str, float]:
    """Planner completion from Bedrock (teacher) or an OpenAI-compatible endpoint (a Qwen planner specialist)."""
    if GENERATOR == "opus":
        client = gsb.boto3.client("bedrock-runtime", region_name=gsb.REGION, config=gsb.BEDROCK_CFG)
        resp = client.converse(modelId=PLANNER_MODEL, messages=[{"role": "user", "content": [{"text": prompt}]}],
                               inferenceConfig={"maxTokens": 3000})
        raw = "\n".join(b["text"] for b in resp["output"]["message"]["content"] if "text" in b)
        u = resp.get("usage", {})
        return raw, (u.get("inputTokens", 0) * gsb.PRICE["opus"][0] + u.get("outputTokens", 0) * gsb.PRICE["opus"][1]) / 1e6
    body = json.dumps({"model": GEN_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 3000,
                       "temperature": 0.7, "top_p": 0.8, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(ENDPOINT.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"], 0.0


def plan_theme(theme: str, cands: dict[str, list[str]]) -> tuple[dict, dict, float, dict]:
    """-> (briefs, picked, cost, stats). stats records how well the planner followed the output contract, so a
    distilled planner can be scored on structure (valid json / in-range index / verbatim brief) as well as taste."""
    block = "\n\n".join(f"## {seg}\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(cands[seg])) for seg in SEGMENT_ORDER)
    raw, cost = ask(PROMPT.format(theme=theme, candidates=block))
    stats = {"json": False, "segments": 0, "bad_index": 0, "reworded_body": 0, "mood_changed": 0}
    try:
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        stats["json"] = True
    except Exception:  # noqa: BLE001
        return {}, {}, cost, stats
    briefs, picked = {}, {}
    for seg in SEGMENT_ORDER:
        entry = data.get(seg)
        if not isinstance(entry, dict) or "index" not in entry:
            continue
        stats["segments"] += 1
        try:
            idx = int(entry["index"])
        except Exception:  # noqa: BLE001
            idx = -1
        if not 0 <= idx < len(cands[seg]):
            stats["bad_index"] += 1
            idx = 0
        text = str(entry.get("brief", "")).strip() or cands[seg][idx]
        # guard the in-distribution promise: everything before "Mood:" must match the picked candidate
        if strip_mood(text) != strip_mood(cands[seg][idx]):
            stats["reworded_body"] += 1
            text = cands[seg][idx]
        elif text.strip() != cands[seg][idx].strip():
            stats["mood_changed"] += 1
        briefs[seg], picked[seg] = text, idx
    return briefs, picked, cost, stats


def main() -> None:
    global GENERATOR, ENDPOINT, GEN_MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", action="append", default=[], help="explicit theme text (repeatable)")
    ap.add_argument("--themes", type=int, default=0, help="instead: sample this many themes from theme_briefs")
    ap.add_argument("--themes-seed", type=int, default=1, help="1 = held-out planner eval themes, 2 = planner training")
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates", type=int, default=12)
    ap.add_argument("--seed", type=int, default=41, help="candidate sampling seed (eval briefs use seed 1)")
    ap.add_argument("--generator", choices=["opus", "spec"], default="opus")
    ap.add_argument("--endpoint", default="http://localhost:8001/v1")
    ap.add_argument("--gen-model", default="planner")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    GENERATOR, ENDPOINT, GEN_MODEL = args.generator, args.endpoint, args.gen_model

    themes = list(args.theme)
    if args.themes:
        themes += [theme_briefs.brief_text(t) for t in theme_briefs.sample(args.themes, args.themes_seed)]
    if not themes:
        ap.error("pass --theme and/or --themes")

    def one(i_theme):
        i, theme = i_theme
        cands = candidates(args.candidates, args.seed + i)
        briefs, picked, cost, stats = plan_theme(theme, cands)
        return {"id": f"scene-{i:03d}", "theme": theme, "briefs": briefs, "picked": picked,
                "stats": stats, "cost": round(cost, 4), "candidates": cands}

    with ThreadPoolExecutor(args.workers) as ex:
        scenes = list(ex.map(one, enumerate(themes)))
    total = sum(s["cost"] for s in scenes)
    ok = sum(1 for s in scenes if s["stats"]["json"] and s["stats"]["segments"] == len(SEGMENT_ORDER)
             and not s["stats"]["bad_index"] and not s["stats"]["reworded_body"])
    for s in scenes:
        print(f"{s['id']}: {s['theme'][:70]} | stats {s['stats']}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": PLANNER_MODEL if args.generator == "opus" else args.gen_model,
                               "generator": args.generator, "scenes": scenes}, indent=2))
    print(f"wrote {out} ({len(scenes)} scenes, contract-clean {ok}/{len(scenes)}, ${total:.3f})")


if __name__ == "__main__":
    main()
