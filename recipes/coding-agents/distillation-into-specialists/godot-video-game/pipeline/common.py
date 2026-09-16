"""Shared helpers for the specialist pipeline: paths, Bedrock calls, run dirs."""
import base64
import json
import os
import re
import time
from pathlib import Path

from config import (AWS_REGION as REGION, DIRECTOR_MODEL, GAME, GODOT,  # noqa: F401
                    JUDGE_MODEL, TEACHER_MODEL)

PIPE = Path(__file__).resolve().parent
ROOT = PIPE.parent
RUNS = PIPE / "runs"

CONTRACT_VERSION = "v1.3"

# When a profile rejects calls in a transient window, try these in order.
FALLBACKS = {
    "us.anthropic.claude-fable-5-1": ["global.anthropic.claude-fable-5-1", "us.anthropic.claude-sonnet-5"],
    "us.anthropic.claude-sonnet-5": ["global.anthropic.claude-sonnet-5"],
}

SEGMENTS = {
    # segment -> (world used for verification, capture shots, capture script)
    # drags are held (~s) past the shot so the camera has not eased back yet
    # pass bar from Marc's labels (anchors/anchor3.jsonl, 2026-09-16): he accepted all 24 sampled layers,
    # including every one the judge scored 5. Agreement with the judge is 6/24 at its own bar of 7 and
    # 18/24 at 6; 6 is the conservative reading, since the set had no rejections to locate his floor.
    "sky": {"world": "beach", "shots": "3,6,9", "script": "4:Drag_0_-220~2.5,7:Drag_-320_0~2.5",
            "pass_bar": {"overall": 6, "min_attribute": 4}},
    # placement segments: default view, then the camera turned to the landward
    # side (negative dx turns left; the beach's promenade and furniture are on
    # the left) and slightly up so tall plants fit, then back along that side
    "vegetation": {"world": "beach", "shots": "3,6,9", "script": "4:Drag_-330_-110~2.5,7:Drag_-200_-30~2.5",
                   "script_by_world": {"street": "4:Drag_-200_-90~2.5,7:Drag_400_-40~2.5"},
                   # judged by Opus 5 with reference frames: on Marc's 28 anchor labels (pipeline/anchors/anchor1.jsonl)
                   # Opus + reference agreed on 22 at the 7/4 bar, Sonnet 5 + reference on 9, the Sep 13 Fable judge on 19
                   "judge_model": "us.anthropic.claude-opus-5",
                   # the Sonnet 5 judge scored vegetation ~2 points below the Sep 13 judge on the same frames
                   # (veg1 sample: 20/40 passes -> 1/40); the shipped layer anchors scale and density
                   "reference": {"beach": "a line of tall thin fan palms along the promenade every 6 to 8 m, a few fuller coconut palms "
                                          "on the upper sand, low hedges; mature size, normal density",
                                 "street": "palms and leafy trees alternating along both verges every 10 to 17 m, hedges and low "
                                           "shrubs along the lot fronts; mature size, normal density"},
                   "reference_note": ("The reference is not what the brief asks for; it shows how the shipped vegetation reads "
                                      "from these three views. Plants stand well back from the camera here, so trunks look thin "
                                      "and crowns small, and a promenade of similar palms repeats along a row: those are the "
                                      "scene's look, not the candidate's defects unless the candidate makes them worse. Judge "
                                      "size, density and species mix relative to the reference: 'giant' should read clearly "
                                      "taller and fuller than it, 'young' smaller, 'dense' fuller, 'sparse' emptier. Calibration: "
                                      "for a brief that described the reference look exactly, the reference frames would score 7 "
                                      "on every attribute. Score above 7 where the candidate matches its brief better than the "
                                      "reference matches its own description, below 7 where it is worse or wrong.")},
    # street furniture is small and near the kerb: look along the sidewalk ahead, then back along the
    # near kerb toward the crosswalk, then back across both kerbs (single per-block items are often out of view)
    "props": {"world": "beach", "shots": "3,6,9", "script": "4:Drag_-300_-40~2.5,7:Drag_-230_20~2.5",
              "script_by_world": {"street": "4:Drag_580_-40~2.5,7:Drag_-230_-20~2.5"},
              "views_by_world": {"street": ["default chase view along the sidewalk", "low view back along the near kerb toward the crosswalk",
                                            "wider view back across both kerbs"]},
              # judged by Opus 5 with reference frames in both worlds (Marc's anchor labels, 2026-09-14: Opus + reference
              # agreed on 22 of 28 at the 7/4 bar). Street: items are too small to see from these views without the
              # shipped block for scale. Beach: with the Sonnet 5 judge the reference made verdicts lower; with Opus it helps.
              "judge_model": "us.anthropic.claude-opus-5",
              "reference": {"street": "lamps with curved arms every 12 m on both kerbs, wooden power poles with wires on the verge, "
                                      "dark green bins, red hydrants, a STOP sign and street-name sign at the crosswalk, a blue bus bench, a mailbox",
                            "beach": "dense rows of white loungers with coloured fabric parallel to the shore, large multi-panel umbrellas "
                                     "in bright and pastel colour sets, towels, buckets, bags and balls between the rows"},
              "reference_note": {
                  "beach": ("The reference is not what the brief asks for; it shows how the shipped beach furniture reads from "
                            "these three views. The rows run back along the shore, so loungers and umbrellas further down the "
                            "beach are small and overlap, towels and clutter are a few pixels, and similar loungers repeat along "
                            "each row: those are the scene's look, not the candidate's defects unless the candidate makes them "
                            "worse. Judge density, row occupancy, umbrella share and palette relative to the reference: 'dense' "
                            "should read fuller than it, 'sparse' emptier. Calibration: for a brief that described the reference "
                            "look exactly, the reference frames would score 7 on every attribute. Score above 7 where the "
                            "candidate matches its brief better than the reference matches its own description, below 7 where "
                            "it is worse or wrong."),
                  "street": ("The reference is not what the brief asks for; it shows how much of a block's street furniture "
                                 "these three views actually reveal. Small repeated items (bins, hydrants) are a few pixels tall "
                                 "at this distance, are often hidden by the walker, trees and parked cars, and a 40 m stretch holds "
                                 "only one or two of each. Calibration: for a brief that described the reference look exactly, the "
                                 "reference frames would score 7 on every attribute. Count an item type as present when it shows "
                                 "about as often as comparable items do in the reference; lower variety or palette only for item "
                                 "types clearly absent where the reference would show them, wrong or out-of-place items, clones, "
                                 "or wrong colours you can see. Score above 7 where the candidate matches its brief better than "
                                 "the reference matches its own description, below 7 where it is worse or wrong.")}},
    # surface segments on the beach: default view, then the walker stops, turns
    # to the sea and walks to the wet band; the camera tilts down at the feet
    # (wet sand, water's edge, shallows), then turns to look along the shore
    # (ground: beach side; water: sea side). The judge also gets the shipped
    # layer's frames as a colour reference.
    "ground": {"world": "beach", "shots": "3,7,9", "script": "3:ArrowDown,3.2:ArrowRight~0.72,4:ArrowUp,5.8:ArrowDown,6:Look_0_260~1.5,8:Look_-330_-260~1.5",
               "script_by_world": {"street": "4:Drag_0_260~2.5,7:Drag_-330_-200~2.5"},
               "views": ["default view", "tilted down at the walker's feet by the water", "turned to look along the beach"],
               "views_by_world": {"street": ["default view", "tilted down at the ground", "side view"]},
               "reference": {"beach": "warm mid-brown fine-grain sand, a 10 m darker wet band with a mirror sheet at the tide line, a few shells along the tide line",
                             "street": "worn grey asphalt, double yellow centre line, white edge lines, plain concrete kerbs and slab sidewalks, mown lawns"}},
    "water": {"world": "beach", "shots": "3,7,9", "script": "3:ArrowDown,3.2:ArrowRight~0.72,4:ArrowUp,5.8:ArrowDown,6:Look_0_260~1.5,8:Look_330_-260~1.5",
              "views": ["default view", "tilted down at the walker's feet by the water", "turned to look along the shore, sea on the left"],
              # pass from the judge's scores, not its own pass flag (Marc's anchor set 2, Sep 15: at the rubric's
              # bar of 7 the judge agreed with him on 17 of 24 water layers; at overall 6 with no attribute below 4, on 20)
              "pass_bar": {"overall": 6, "min_attribute": 4},
              "reference": {"beach": "gentle swell, turquoise tropical water, a lacy foam band at the edge with sand showing between the patches, sparse foam lines further out"}},
    # the assembled scene, judged as a whole by verify_composite(): the vegetation views show sky, ground and
    # plants together; the sky's tilted-up views show the weather and the light. Opus judges, the shipped scene
    # is the reference, and the verdict blames segments so the director can send revision briefs.
    "composite": {"world": "beach", "judge_model": "us.anthropic.claude-opus-5",
                  "recipes": [{"shots": "3,6,9", "script": "4:Drag_-330_-110~2.5,7:Drag_-200_-30~2.5",
                               "script_by_world": {"street": "4:Drag_-200_-90~2.5,7:Drag_400_-40~2.5"}},
                              {"shots": "3,6,9", "script": "4:Drag_0_-220~2.5,7:Drag_-320_0~2.5"}],
                  "views": ["default chase view", "turned to one side and up", "looking back along the scene",
                            "default chase view again", "tilted up at the sky", "turned to the side, sky and horizon"],
                  "reference": {"beach": "the normal game beach: every shipped layer (sky, sand, sea, palms, furniture, crowd)",
                                "street": "the normal game street: every shipped layer (sky, road and lawns, trees, furniture, traffic)"},
                  "reference_note": ("The reference is the normal game scene with every shipped layer, under the same views. It is not "
                                     "what the scene brief asks for; it shows how this game renders a coherent scene, and its low-poly "
                                     "style, hard shadows and draw distance are not defects. Calibration: the reference frames would "
                                     "score 7 on coherence, integration and artifacts. Judge the candidate as one picture: do the new "
                                     "layers agree with each other and with the layers that stayed shipped, and does the whole match "
                                     "the scene brief?")},
}
# load() paths a segment's candidates may use (everything else is forbidden)
ALLOWED_LOADS = {
    "ground": ["res://segments/ground/shaders/sand.gdshader", "res://segments/ground/shaders/asphalt.gdshader"],
    "water": ["res://segments/water/shaders/water.gdshader"],
}


def run_dir(name: str) -> Path:
    d = RUNS / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def read(p) -> str:
    return Path(p).read_text()


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def extract_code(text: str) -> str:
    """Return the body of the first fenced gdscript block, or the whole text."""
    # greedy to the LAST fence: a nested fence inside the block would otherwise end it early
    m = re.search(r"```(?:gdscript|gd)?\s*\n(.*)```", text, re.S)
    if not m:
        # no closing fence: a reply cut off at the token limit. Keep what was written
        # after the opening fence so the gates report the real problem, not an empty file.
        m = re.search(r"```(?:gdscript|gd)?\s*\n(.*)", text, re.S)
    body = (m.group(1) if m else text)
    # models sometimes nest a second fence inside the first: drop any fence lines
    body = "\n".join(l for l in body.splitlines() if not l.strip().startswith("```"))
    return body.strip() + "\n"


_client = None


def bedrock():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config
        # long generations are fine, hung sockets are not: bounded read timeout, SDK retries off (we retry ourselves)
        _client = boto3.client("bedrock-runtime", region_name=REGION,
                               config=Config(connect_timeout=10, read_timeout=240, retries={"max_attempts": 1}))
    return _client


def converse(model: str, system: str, user_blocks, max_tokens=9000, temperature=None, retries=4):
    """One Bedrock Converse call. user_blocks is a list of {"text":..} or
    {"image": {"format": "png", "source": {"bytes": ...}}} blocks.
    Claude 5 models reject `temperature`; it is only sent when explicitly
    given for an older model."""
    cfg = {"maxTokens": max_tokens}
    if temperature is not None and "claude-5" not in model and "fable" not in model and "sonnet-5" not in model:
        cfg["temperature"] = temperature
    kwargs = dict(
        modelId=model,
        messages=[{"role": "user", "content": user_blocks}],
        inferenceConfig=cfg,
    )
    if system:
        kwargs["system"] = [{"text": system}]
    # transient service errors (throttling, brief model-side outages) can last
    # minutes: up to ~4 minutes of backoff before giving up
    delays = [3, 8, 15, 30, 60, 90]
    fallbacks = list(FALLBACKS.get(model, []))   # tried in order when the model rejects the call outright
    for attempt in range(len(delays) + 1):
        try:
            r = bedrock().converse(**kwargs)
            text = "".join(b.get("text", "") for b in r["output"]["message"]["content"])
            return text, r.get("usage", {})
        except Exception as e:
            msg = str(e)
            # a model-side rejection that comes and goes ("data retention mode ... not
            # available"): switch to the next profile / model before waiting
            if "retention" in msg and fallbacks:
                nxt = fallbacks.pop(0)
                print(f"  bedrock: {kwargs['modelId']} rejected the call; switching to {nxt}", flush=True)
                kwargs["modelId"] = nxt
                continue
            if attempt >= len(delays):
                raise
            print(f"  bedrock retry {attempt + 1}: {msg[:120]}", flush=True)
            time.sleep(delays[attempt])


def image_block(path) -> dict:
    return {"image": {"format": "png", "source": {"bytes": Path(path).read_bytes()}}}


def parse_json(text: str):
    """Tolerant JSON extraction from a model reply: fenced block, raw_decode
    from the first brace (ignores trailing prose), then a greedy match."""
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    if start >= 0:
        try:
            return json.JSONDecoder().raw_decode(text[start:])[0]
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)
