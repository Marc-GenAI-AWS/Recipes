"""Brief-adherence vision judge: does the rendered layer look like what its brief asked for?

The mechanical checks (gates, greycard, presence) prove a layer renders; they cannot tell
"scattered cumulus, hard sun" from a flat haze. This asks Fable (Bedrock, image input) to
score each labelled clause of the brief against the captured frames of the assembled scene.

  judge_brief("sky", brief_text, screenshots) -> (ok, {"elements": {...}, "mean": .., "cost": ..})

Scores per clause: 0 absent or contradicted · 1 faint hint · 2 clearly present · 3 convincing.
Pass: no visible clause scores 0 and the non-mood clauses average >= MIN_MEAN. Mood is scored
and reported but not gated (too subjective for a hard threshold). Calibrate before gating:
scenes/phase1/calib_brief_judge.py.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "phase1"))
import gen_sky_baseline as gsb  # noqa: E402  (Bedrock client config, model id, region)

# Calibrated 2026-09-14 on sky-view frames (5 cases, small — recalibrate on more before gating
# training data): original High Park sky vs a describing brief mean 1.5 (Clouds 1); Fable sky-010
# vs its brief 1.0 (Clouds 1); original vs a clear starry brief 0.33 (Clouds 0); old specialist
# sky-003 / sky-020 1.0 / 0.67 (Clouds 0, featureless wash). This renderer's clouds are soft, so
# the judge rarely gives 2-3; "no non-mood clause at 0" is what separates the cases.
MIN_MEAN = 1.0
# Opus 5, not the Fable teacher: a general judge (design doc) and far better Bedrock availability
# (2026-09-14: Fable 2/3 calls at 6–13 s vs Opus 5 3/3 at ~1 s during a ServiceUnavailable episode)
JUDGE_MODEL = os.environ.get("BRIEF_JUDGE_MODEL", "us.anthropic.claude-opus-5")
# set to an OpenAI-compatible /v1 (a served vision model) to run the judge off Bedrock entirely
JUDGE_ENDPOINT = os.environ.get("BRIEF_JUDGE_ENDPOINT", "")
JUDGE_VIEW = HERE / "phase1" / "judge_view"   # sky-view camera + no-op mist/rain overrides
STATES = ("first-light", "cloud-shadows", "storm-break")   # highpark's captured states
LAYER_WORDS = {"sky": "the SKY (dome above the mountains: clouds, sun, atmosphere)",
               "ground": "the GROUND surface of the meadow", "camera": "the CAMERA framing and move",
               "vegetation": "the GRASS", "fauna": "the HERD of animals", "effects": "the MIST",
               "ocean": "the WATER SURFACE (sea state, wave shape, water colour, foam, surface light)"}
# each host frames a different world and captures different state names. Judging an ocean as "a
# mountain-prairie basin" scores the wrong thing, and the image loop below used to iterate the
# highpark STATES tuple — on any other host that attached NO images and the judge scored blind.
# Descriptors are DERIVED, not hardcoded per segment, so a new scene/segment needs no edit here:
#   1. the segment registry entry's optional "judge" dict wins  ({"layer": ..., "scene": ..., "states": ...})
#   2. else the scene's manifest.json "title" describes the world ("Sea State — an open ocean seen from a ship's bow")
#   3. else these defaults
DEFAULT_SCENE = ("a mountain-prairie basin", "three lighting states (dawn, bright windy, dark storm)")

# WHOLE-FRAME ONLY. Measured 2026-09-16 on 353 judged layers (data/judge_data): the separation between a layer judged
# against its OWN brief and against a different brief of the same segment was camera +0.32, ocean +0.18, fauna +0.11,
# effects +0.08, vegetation -0.00, sky -0.01, ground -0.11. Only properties that fill the frame are discriminable at this
# camera distance and resolution — a ~16 px herd or a soft haze scores "faint hint" whatever the brief says, so a score
# there is noise dressed as a measurement. The judge therefore refuses segments it cannot see, rather than returning a
# number nobody should trust. Re-measure with collect_judge_data.py before adding one.
JUDGE_SEGMENTS = {s.strip() for s in os.environ.get("BRIEF_JUDGE_SEGMENTS", "camera,ocean").split(",") if s.strip()}
MEASURED_SEPARATION = {"camera": 0.32, "ocean": 0.18, "fauna": 0.11, "effects": 0.08,
                       "vegetation": -0.00, "sky": -0.01, "ground": -0.11}


def describe(segment: str, shots: dict | None = None) -> tuple[str, str, str]:
    """(scene words, states words, layer words) for the rubric."""
    seg = {}
    try:
        from segments import SEGMENTS
        seg = SEGMENTS.get(segment, {})
    except Exception:  # noqa: BLE001  (judge is usable standalone, e.g. in calibration scripts)
        pass
    j = seg.get("judge", {})
    scene_name = seg.get("scene")
    scene_desc = j.get("scene")
    if not scene_desc and scene_name:
        try:
            title = json.loads((HERE / scene_name / "manifest.json").read_text()).get("title", "")
            scene_desc = title.split("—", 1)[1].strip() if "—" in title else title
        except Exception:  # noqa: BLE001
            scene_desc = None
    states_desc = j.get("states")
    if not states_desc:
        names = [st for st in (STATES if shots is None else shots) if shots is None or st in shots]
        states_desc = f"these states: {', '.join(names)}" if names else DEFAULT_SCENE[1]
    layer_desc = (j.get("layer") or LAYER_WORDS.get(segment)
                  or (f"the {seg['layer_name'].upper()}" if seg.get("layer_name") else f"the {segment.upper()} layer"))
    return scene_desc or DEFAULT_SCENE[0], states_desc, layer_desc

RUBRIC = """You are judging whether one layer of a rendered 3D scene matches the brief it was written from.
The scene is {scene}. Judge ONLY {layer}; ignore every other part of the scene.
The frames show the same scene under {states} — the
brief's features should be recognisable in most of them, allowing for each state's lighting.

BRIEF CLAUSES:
{clauses}

Score EACH clause from what is visible:
  0 = absent or contradicted   1 = faint hint only   2 = clearly present   3 = convincing
Be strict: a uniform haze is NOT "scattered cumulus"; a soft glow is NOT "a bright hard sun".

Output STRICT JSON only:
{{"scores": {{"<clause label>": n, ...}}, "most_wrong": "<one sentence>"}}"""


def clauses(brief: str) -> dict[str, str]:
    """'Clouds: a..  Sun: b..  Mood: c..' -> {"Clouds": "a..", ...}"""
    parts = re.split(r"(?:^|\s)([A-Z][A-Za-z]+):\s", brief)
    return {parts[i]: parts[i + 1].strip().rstrip(".") for i in range(1, len(parts) - 1, 2)}


def _jpeg(png: bytes, w: int = 640, top: float | None = None) -> bytes:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    if top:   # judge at the right scale: the sky band only, at native resolution (no downscale)
        img = img.crop((0, 0, img.width, int(img.height * top)))
    else:
        img = img.resize((w, int(img.height * w / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def skyview_shots(candidate: str | None) -> dict:
    """Render a sky candidate (None = the host's own sky) into High Park with the judging camera
    pitched up at the sky and no mist/rain; returns {state: [png, ...]}. The gates are NOT read
    from this render (the near-static camera fails 'animates') — it only feeds the judge."""
    import subprocess
    import tempfile
    sys.path.insert(0, str(HERE))
    from layer_harness import render_robust
    out = Path(tempfile.mkdtemp(prefix="skyview-")) / "skyview.cdn.html"
    cmd = ["node", str(HERE / "assemble.cjs"), "highpark",
           "--set", f"camera.js={JUDGE_VIEW / 'skyview_camera.js'}",
           "--set", f"layers/mist.js={JUDGE_VIEW / 'noop_mist.js'}",
           "--set", f"layers/rain.js={JUDGE_VIEW / 'noop_rain.js'}"]
    if candidate:
        cmd += ["--set", f"layers/atmosphere.js={Path(candidate).resolve()}"]
    r = subprocess.run(cmd + ["--out", str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"sky-view assemble failed: {r.stdout[-300:]} {r.stderr[-300:]}")
    return render_robust(out.read_text()).screenshots


def _ask(content: list, max_tokens: int) -> tuple[str, float]:
    """Send the rubric + frames to whichever judge backend is configured.

    Default: Bedrock (Opus 5). Set JUDGE_ENDPOINT to an OpenAI-compatible /v1 served by a VISION model
    (e.g. a Qwen3.5 VLM on vLLM) to run the judge locally at no per-call cost — the intended path once a
    small judge is distilled from the Opus scores. JUDGE_MODEL then names the served model.
    """
    if JUDGE_ENDPOINT:
        import base64
        msg = []
        for c in content:
            if "text" in c:
                msg.append({"type": "text", "text": c["text"]})
            else:
                b64 = base64.b64encode(c["image"]["source"]["bytes"]).decode()
                msg.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        body = json.dumps({"model": JUDGE_MODEL, "messages": [{"role": "user", "content": msg}],
                           "max_tokens": max_tokens, "temperature": 0.0,
                           "chat_template_kwargs": {"enable_thinking": False}}).encode()
        req = urllib.request.Request(JUDGE_ENDPOINT.rstrip("/") + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"], 0.0

    client = gsb.boto3.client("bedrock-runtime", region_name=gsb.REGION, config=gsb.BEDROCK_CFG)
    # same backoff as gen_segment: Fable ServiceUnavailable episodes outlast boto's 3 retries
    import random
    import time
    for k in range(6):
        try:
            resp = client.converse(modelId=JUDGE_MODEL, messages=[{"role": "user", "content": content}],
                                   inferenceConfig={"maxTokens": max_tokens})
            break
        except Exception as e:  # noqa: BLE001
            transient = any(s in str(e) for s in ("ServiceUnavailable", "Throttl", "ModelNotReady",
                                                  "InternalServer", "timed out", "Read timeout"))
            if k == 5 or not transient:
                raise
            time.sleep(min(300, 20 * 2 ** k) * (0.7 + 0.6 * random.random()))
    text = "\n".join(b["text"] for b in resp["output"]["message"]["content"] if "text" in b)
    usage = resp.get("usage", {})
    pin, pout = gsb.PRICE["fable"] if "fable" in JUDGE_MODEL else gsb.PRICE["opus"]
    return text, (usage.get("inputTokens", 0) * pin + usage.get("outputTokens", 0) * pout) / 1e6


def judge_brief(segment: str, brief: str, shots: dict, max_tokens: int = 3000):
    if segment not in JUDGE_SEGMENTS:
        return True, {"skipped": f"{segment} is not a whole-frame segment: measured match-vs-mismatch separation "
                                 f"{MEASURED_SEPARATION.get(segment, 'unmeasured')}, too small to score honestly",
                      "scores": {}, "mean": None, "cost": 0.0}
    cl = clauses(brief)
    if not cl:
        return False, {"error": "brief has no labelled clauses"}
    scene_desc, states_desc, layer_desc = describe(segment, shots)
    content = [{"text": RUBRIC.format(scene=scene_desc, states=states_desc, layer=layer_desc,
                                      clauses="\n".join(f"- {k}: {v}" for k, v in cl.items()))}]
    # sky: in the scene camera's frames the sky is a thin band behind mist, fog and horizon haze —
    # even the original High Park cumulus scored Clouds 1 ("uniform milky haze"), cropped or not.
    # Callers pass sky-view frames instead (skyview_shots: camera pitched up, no mist, no rain).
    if segment == "sky":
        content[0]["text"] += ("\n\nThese frames come from a JUDGING camera pitched up at the sky, with the ground "
                               "mist and rain removed, so the sky fills the frame; the mountain ridge is at the "
                               "bottom edge.")
    # prefer highpark's state order when present, else whatever states this host captured (max 3)
    order = [st for st in STATES if st in shots] or sorted(shots)[:3]
    for st in order:
        pair = shots.get(st)
        if pair:
            content.append({"text": f"[state: {st}]"})
            content.append({"image": {"format": "jpeg", "source": {"bytes": _jpeg(pair[0], w=800)}}})
    if not any("image" in c for c in content):
        return False, {"error": "no frames to judge"}
    text, cost = _ask(content, max_tokens)
    m = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    raw = data.get("scores", data) or {}
    # match the judge's keys to clause labels loosely ("clouds", "Clouds:", "Clouds: a heavy ...")
    norm = {re.sub(r"[^a-z]", "", str(k).lower().split(":")[0]): v for k, v in raw.items()}

    def score_for(label: str) -> int:
        v = norm.get(re.sub(r"[^a-z]", "", label.lower()))
        try:
            return max(0, min(3, int(float(v))))
        except (TypeError, ValueError):
            return 0
    scores = {k: score_for(k) for k in cl}
    gated = {k: v for k, v in scores.items() if k.lower() != "mood"}
    mean = sum(gated.values()) / max(1, len(gated))
    ok = bool(gated) and min(gated.values()) >= 1 and mean >= MIN_MEAN
    return ok, {"scores": scores, "mean": round(mean, 2), "min_mean": MIN_MEAN,
                "most_wrong": str(data.get("most_wrong", ""))[:200], "cost": round(cost, 4),
                "raw": text[:300]}
