"""The verifier: static gate -> runtime gate -> checks -> capture -> judge -> aggregate.

    python3 pipeline/verify.py --candidates runs/sky1/candidates.jsonl --out runs/sky1
    python3 pipeline/verify.py --file some_layer.gd --segment sky --brief '{"...": ...}'

One pipeline serves three consumers: data filtering (pass flag), training
(score in [0, 1]) and the director's acceptance test (evidence strings).
Gates veto: a failed gate scores 0 regardless of the judge.

Rendering is native (Godot on the local GPU display) when DISPLAY is set,
which takes seconds; the browser harness in shots/ is the fallback recipe.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import (ALLOWED_LOADS, GAME, GODOT, JUDGE_MODEL, PIPE, SEGMENTS, converse, image_block, parse_json, read,
                    read_jsonl, write_jsonl)

FORBIDDEN = ["OS.", "FileAccess", "DirAccess", "HTTPRequest", "JavaScriptBridge", "get_tree().quit",
             "load(", "preload(", "class_name "]
BASELINE = {}   # world -> stats without overrides
GPU_LOCK = threading.RLock()   # one native capture at a time; gates and judge calls overlap


# ---------------------------------------------------------------- gates ---

def static_gate(code: str, segment: str = "") -> list:
    problems = []
    for path in ALLOWED_LOADS.get(segment, []):
        code = code.replace(f'load("{path}")', "ALLOWED_LOAD")
    if segment in ("ground", "water"):
        for tok in ("Shader.new(", "shader.code", "shader_type"):
            if tok in code:
                problems.append(f"forbidden for this segment: {tok} (set the shipped shader's uniforms instead)")
    # leading comments and blank lines are fine before `extends`
    head = "\n".join(l for l in code.splitlines() if l.strip() and not l.strip().startswith("#")).lstrip()
    if not (head.startswith("extends SceneLayer") or head.startswith("extends ChunkedLayer")):
        problems.append("file must start with 'extends SceneLayer' or 'extends ChunkedLayer'")
    if head.startswith("extends ChunkedLayer") and "func build_chunk(" not in code:
        problems.append("a ChunkedLayer must implement build_chunk(chunk, rng)")
    if "func build(" not in code and "func build_chunk(" not in code:
        problems.append("no build() function")
    for tok in FORBIDDEN:
        if tok in code:
            problems.append(f"forbidden token: {tok.strip()}")
    if len(code) > 20000:
        problems.append("file longer than 20k chars")
    try:   # unknown engine / project constants, wrong built-in constructor arity (gdcheck.py); never blocks on its own bug
        from gdcheck import check
        problems += check(code)
    except Exception as e:
        print(f"  gdcheck skipped ({str(e)[:120]})", flush=True)
    return problems


def install_candidate(segment: str, cid: str, code: str) -> str:
    d = GAME / "segments" / segment / "candidates"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cid}.gd").write_text(code)
    return f"res://segments/{segment}/candidates/{cid}.gd"


# Every Godot run gets a data-segment cap: a generated layer with an endless allocating loop
# grew one process to 91 GB on 2026-09-14 and the kernel OOM-killed the whole run. Normal gates
# and captures peak near 1 GB. A capped runaway fails its allocations and then hits the timeout.
GODOT_MEM_BYTES = int(float(os.environ.get("GODOT_MEM_GB", "8")) * 1024 ** 3)
_PRLIMIT = shutil.which("prlimit")


def godot(args, timeout, display=None):
    env = dict(os.environ)
    if display:
        env["DISPLAY"] = display
    cmd = [str(GODOT), "--path", str(GAME)] + args
    if _PRLIMIT:
        cmd = [_PRLIMIT, f"--data={GODOT_MEM_BYTES}"] + cmd
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    return p.stdout + p.stderr + f"\n[exit {p.returncode}]"


def _gate_hints(out: str, swap: str) -> list:
    """Type-inference errors quoted with their source line and the typed declaration to write:
    the specialists repeated Godot's bare "Cannot infer the type" error across every revision."""
    code_lines = []
    if ":" in swap and swap.split(":", 1)[1].startswith("res://"):
        p = GAME / swap.split(":", 1)[1][len("res://"):]
        if p.exists():
            code_lines = p.read_text().splitlines()
    lines = out.splitlines()
    hints = []
    for i, l in enumerate(lines):
        m = re.search(r'Cannot infer the type of "(\w+)" variable', l)
        if not m and "inferred from a Variant value" not in l:
            continue
        ln = None
        for nxt in lines[i + 1:i + 4]:
            mm = re.search(r"/candidates/[^():]+\.gd:(\d+)\)", nxt)
            if mm:
                ln = int(mm.group(1))
                break
        src = code_lines[ln - 1].strip() if ln and 0 < ln <= len(code_lines) else ""
        dm = re.match(r"var (\w+)\s*:=\s*(.+)$", src)
        if dm:
            name, expr = dm.group(1), dm.group(2)
            if re.search(r"[<>]=?|==|!=|\band\b|\bor\b|\bnot\b", expr):
                typ = "bool"
            elif re.match(r"(lerp|lerpf|clamp|min|max|abs|sign|snapped|wrap|move_toward|remap)\(", expr) or re.search(r"[-+*/]", expr):
                typ = "float"   # Variant-returning math helpers; here they always carry floats
            else:
                typ = "<its type>"
            hints.append(f"fix line {ln}: `{src[:100]}` has no known type; declare it explicitly: `var {name}: {typ} = {expr[:70]}`")
        elif ln:
            hints.append(f"fix line {ln}: `{src[:100]}` produces a value with no known type; declare the variable with an explicit type")
    return list(dict.fromkeys(hints))


def runtime_gate(world: str, swap: str) -> tuple:
    out = godot(["--headless", "--quit-after", "90", "--", f"--world={world}", f"--swap={swap}"], timeout=180)
    if 'Parameter "mem" is null' in out or "realloc_static" in out:
        return (False, [f"ran out of memory above the {GODOT_MEM_BYTES / 1024 ** 3:.0f} GB cap while building "
                        "(an endless loop that keeps allocating?)"])
    errors = [l.strip() for l in out.splitlines() if "SCRIPT ERROR" in l or l.startswith("ERROR") or "Parse Error" in l]
    ready = "world ready" in out
    if not ready and not errors:
        errors.append("scene never reported 'world ready'")
    LAST_GATE_OUTPUT[0] = out
    hints = _gate_hints(out, swap) if errors else []
    return (len(errors) == 0, (hints + errors)[:8])


LAST_GATE_OUTPUT = [""]


def contact_lines(out: str) -> dict:
    """Parse the crowd contact validator lines printed by the headless run."""
    res = {}
    for l in out.splitlines():
        m = re.match(r"contacts (\w+)\s+n=\s*(\d+)\s+max penetration ([\d.]+) cm\s+max hover ([\d.]+) cm\s+(OK|FAIL)", l.strip())
        if m:
            res[m.group(1)] = {"n": int(m.group(2)), "pen_cm": float(m.group(3)), "hover_cm": float(m.group(4)), "ok": m.group(5) == "OK"}
    return res


# --------------------------------------------------------------- capture ---

def capture(world: str, swap: str, out_dir: Path, shots: str, script: str) -> dict:
    display = os.environ.get("CAPTURE_DISPLAY") or os.environ.get("DISPLAY") or ":0"
    out_dir = Path(out_dir).resolve()          # Godot chdirs into the project; relative paths would land there
    out_dir.mkdir(parents=True, exist_ok=True)
    args = ["--resolution", "1280x720", "--", f"--world={world}", f"--capture={out_dir}", f"--shots={shots}"]
    if script:
        args.append(f"--script={script}")
    if swap:
        args.append(f"--swap={swap}")
    out = godot(args, timeout=240, display=display)
    stats_p = out_dir / "stats.json"
    if not stats_p.exists():
        raise RuntimeError("capture produced no stats.json (args %s):\n%s" % (args, out[-800:]))
    stats = json.loads(stats_p.read_text())
    stats["frames"] = sorted(str(p) for p in out_dir.glob(f"{world}_*s.png"))
    return stats


def baseline(world: str, shots: str, script: str, segment: str = "") -> dict:
    key = f"{world}_{segment}"
    if key not in BASELINE:
        d = PIPE / "runs" / "_baseline" / key
        p = d / "stats.json"
        if p.exists():
            st = json.loads(p.read_text())
            st["frames"] = sorted(str(x) for x in d.glob(f"{world}_*s.png"))
        else:
            st = capture(world, "", d, shots, script)
        BASELINE[key] = st
    return BASELINE[key]


# ---------------------------------------------------------------- checks ---

def sky_checks(brief: dict, stats: dict, base: dict) -> tuple:
    """Numeric facts a sky layer must get right. Returns (score 0..1, notes)."""
    notes, scores = [], []
    pal = stats["palette"]
    sd = pal["sun_dir"]
    elev = math.degrees(math.asin(max(-1.0, min(1.0, -sd[1]))))
    want = brief.get("sun_elevation_deg", 45.0)
    if want < 0.0:
        # sun below the horizon: the light is the moon / fill, anywhere 10-60 deg up
        ok = 10.0 <= elev <= 60.0
        scores.append(1.0 if ok else 0.4)
        notes.append(f"night: light elevation {elev:.0f} deg ({'ok' if ok else 'outside 10-60'})")
    else:
        d = abs(elev - want)
        scores.append(max(0.0, 1.0 - d / 25.0))
        notes.append(f"sun elevation {elev:.0f} deg vs brief {want:.0f} ({'ok' if d < 8 else 'off by %.0f' % d})")
    # azimuth of the sun's position: 0 = towards -Z, 90 = +X (light travels the other way)
    az = (math.degrees(math.atan2(-sd[0], sd[2])) + 360.0) % 360.0
    want_az = brief.get("sun_azimuth_deg", 0.0)
    da = min(abs(az - want_az), 360 - abs(az - want_az))
    scores.append(max(0.0, 1.0 - da / 60.0))
    notes.append(f"sun azimuth {az:.0f} vs brief {want_az:.0f} ({'ok' if da < 20 else 'off by %.0f' % da})")
    # palette published (changed from the defaults unless it's the default kind of day)
    default = [0.1, 0.32, 0.82]
    moved = sum(abs(a - b) for a, b in zip(pal["sky_zenith"], default)) > 0.05
    if brief.get("time_of_day") in ("noon", "morning") and brief.get("weather") == "clear":
        scores.append(1.0)
    else:
        scores.append(1.0 if moved else 0.3)
        notes.append("palette published" if moved else "sky_zenith left at the default")
    # budget
    added = stats["draw_calls"] - base["draw_calls"]
    scores.append(1.0 if added <= 40 else max(0.0, 1.0 - (added - 40) / 80.0))
    notes.append(f"draw calls {added:+d} vs the shipped sky (budget +40), fps {stats['fps_avg']:.0f}")
    if stats["fps_avg"] < 60:
        scores.append(0.3)
        notes.append("below 60 fps")
    # night must not be black: mean brightness of the tilted-up frame
    try:
        from PIL import Image
        im = Image.open(stats["frames"][1]).convert("L").resize((64, 36))
        top = sum(im.getpixel((x, y)) for x in range(64) for y in range(12)) / (64 * 12) / 255.0
        tod = brief.get("time_of_day")
        if tod == "night":
            ok = 0.02 < top < 0.35
        elif tod in ("dusk", "dawn"):
            ok = 0.08 < top < 0.7
        else:
            ok = top > 0.25
        scores.append(1.0 if ok else 0.2)
        notes.append(f"upper-sky brightness {top:.2f} ({'plausible' if ok else 'implausible'} for {tod})")
    except Exception as e:
        notes.append(f"brightness check skipped: {e}")
    return sum(scores) / len(scores), notes


def _zone_ok(world: str, x: float, kind: str) -> bool:
    if world == "beach":
        return x < -12.0 if kind == "vegetation" else (-38.0 < x < -11.0)
    ax = abs(x)
    if kind == "vegetation":
        return 9.3 <= ax <= 13.4
    return 6.2 <= ax <= 12.9


def _plants(probe: dict) -> list:
    """Node3D groups (trees, palms, item groups) in chunk 1: [name, class, x, y, z, children]."""
    return [n for n in probe.get("nodes", []) if n[1] == "Node3D"]


def vegetation_checks(brief: dict, stats: dict, base: dict) -> tuple:
    notes, scores = [], []
    world = brief.get("world", "beach")
    pr = stats.get("probe", {}).get("vegetation", {})
    plants = _plants(pr)
    n = len(plants)
    lo, hi = {"sparse": (6, 24), "normal": (12, 44), "dense": (22, 80)}.get(brief.get("density", "normal"), (6, 80))
    in_band = lo <= n <= hi
    scores.append(1.0 if in_band else max(0.0, 1.0 - min(abs(n - lo), abs(n - hi)) / 20.0))
    notes.append(f"{n} plant groups per chunk ({'in' if in_band else 'outside'} the {brief.get('density')} band {lo}-{hi})")
    if n:
        ok = sum(1 for p in plants if _zone_ok(world, p[2], "vegetation"))
        frac = ok / n
        scores.append(frac)
        notes.append(f"{ok}/{n} plants inside the allowed zones")
    added = stats.get("obstacles", 0) - base.get("obstacles", 0)
    scores.append(1.0 if added >= 0.7 * n else 0.5)
    notes.append(f"obstacles registered: {added:+d} vs the shipped layer")
    dc = stats["draw_calls"] - base["draw_calls"]
    scores.append(1.0 if dc <= 150 else max(0.0, 1.0 - (dc - 150) / 200.0))
    notes.append(f"draw calls {dc:+d} vs the shipped layer (budget +150), fps {stats['fps_avg']:.0f}")
    if stats["fps_avg"] < 60:
        scores.append(0.3); notes.append("below 60 fps")
    return sum(scores) / len(scores), notes


def props_checks(brief: dict, stats: dict, base: dict) -> tuple:
    notes, scores = [], []
    world = brief.get("world", "beach")
    pr = stats.get("probe", {}).get("props", {})
    groups = _plants(pr)
    n = len(groups)
    if world == "beach":
        spots = pr.get("spots", -1)
        lo, hi = {"sparse": (80, 150), "normal": (130, 230), "dense": (190, 320)}.get(brief.get("density", "normal"), (80, 320))
        # spots is per-chunk lists appended per chunk; the probe reports the count of chunk lists, so use group count
        in_band = lo <= n <= hi
        scores.append(1.0 if in_band else max(0.0, 1.0 - min(abs(n - lo), abs(n - hi)) / 60.0))
        notes.append(f"{n} furniture groups per chunk ({'in' if in_band else 'outside'} the {brief.get('density')} band {lo}-{hi}); spots lists {spots}")
        scores.append(1.0 if spots == 3 else 0.2)
        if spots != 3:
            notes.append("spots must have one list per chunk (3)")
        contacts = contact_lines(LAST_GATE_OUTPUT[0])
        if contacts:
            worst = max(max(v["pen_cm"], v["hover_cm"]) for v in contacts.values())
            scores.append(1.0 if all(v["ok"] for v in contacts.values()) else max(0.0, 1.0 - worst / 10.0))
            notes.append("crowd contacts: " + ", ".join(f"{k} n={v['n']} pen {v['pen_cm']}cm hover {v['hover_cm']}cm {'OK' if v['ok'] else 'FAIL'}" for k, v in contacts.items()))
        else:
            scores.append(0.3); notes.append("no crowd contact report (nobody could be seated)")
    else:
        lo, hi = {"sparse": (10, 40), "normal": (20, 70), "dense": (40, 120)}.get(brief.get("density", "normal"), (10, 120))
        added_ob = stats.get("obstacles", 0) - base.get("obstacles", 0)
        notes.append(f"{n} node groups per chunk, obstacles {added_ob:+d} vs the shipped layer")
        scores.append(1.0 if added_ob >= -20 else 0.5)
    if n:
        ok = sum(1 for g in groups if _zone_ok(world, g[2], "props"))
        scores.append(ok / n)
        notes.append(f"{ok}/{n} groups inside the allowed zones")
    dc = stats["draw_calls"] - base["draw_calls"]
    scores.append(1.0 if dc <= 40 else max(0.0, 1.0 - (dc - 40) / 100.0))
    notes.append(f"draw calls {dc:+d} vs the shipped layer (budget +40), fps {stats['fps_avg']:.0f}")
    if stats["fps_avg"] < 60:
        scores.append(0.3); notes.append("below 60 fps")
    return sum(scores) / len(scores), notes


def surface_checks(brief: dict, stats: dict, base: dict) -> tuple:
    """Ground / water: a mesh must exist, and the budget must hold; the look is the judge's."""
    notes, scores = [], []
    seg = brief.get("segment", "ground")
    pr = stats.get("probe", {}).get(seg, {})
    meshes = [n for n in pr.get("nodes", []) if n[1] in ("MeshInstance3D", "MultiMeshInstance3D")]
    scores.append(1.0 if meshes else 0.0)
    notes.append(f"{len(meshes)} mesh nodes placed" if meshes else "no mesh placed by the layer")
    dc = stats["draw_calls"] - base["draw_calls"]
    budget = 10 if seg == "ground" else 3
    scores.append(1.0 if dc <= budget else max(0.0, 1.0 - (dc - budget) / 30.0))
    notes.append(f"draw calls {dc:+d} vs the shipped layer (budget +{budget}), fps {stats['fps_avg']:.0f}")
    if stats["fps_avg"] < 60:
        scores.append(0.3); notes.append("below 60 fps")
    return sum(scores) / len(scores), notes


CHECKS = {"sky": sky_checks, "vegetation": vegetation_checks, "props": props_checks, "ground": surface_checks, "water": surface_checks}


def judge_pass(segment: str, j: dict) -> bool:
    """The judge's verdict as a pass flag. A segment with a pass_bar (set from a human anchor set) passes on
    the judge's scores: overall >= the bar and no attribute below the minimum; otherwise the judge's own flag."""
    bar = SEGMENTS.get(segment, {}).get("pass_bar")
    if not bar:
        return bool(j.get("pass"))
    overall = j.get("overall")
    scores = [v.get("score") for v in (j.get("attributes") or {}).values()
              if isinstance(v, dict) and isinstance(v.get("score"), (int, float))]
    return (isinstance(overall, (int, float)) and overall >= bar["overall"]
            and bool(scores) and min(scores) >= bar["min_attribute"])


def checks_evidence(notes: list, cscore: float) -> list:
    """The checks line for the evidence. A failed check leads with what failed and the fix: specialists
    ignored "draw calls +62 vs the shipped layer (budget +10)" when it read like a statistic."""
    lines = []
    if cscore < 0.6:
        lines.append(f"FAILED CHECKS (score {cscore:.2f}, a pass needs 0.60): the layer is rejected whatever the judge scores")
    for n in notes:
        m = re.search(r"draw calls ([+-]\d+) vs .*\(budget \+(\d+)\)", n)
        if m and int(m.group(1)) > int(m.group(2)):
            lines.append(f"FAILED CHECK: draw calls {m.group(1)} is over the +{m.group(2)} budget; merge the geometry into one "
                         "MeshBatch per material (add_box_at / add_box / add_cylinder, then instance or commit_with once) "
                         "instead of a separate MeshInstance3D for each piece")
    return lines + ["checks: " + "; ".join(notes)]


# ----------------------------------------------------------------- judge ---

# how the judge reads reference frames unless the segment spec gives its own note
COLOUR_NOTE = ("The scene's daylight lightens and cools every colour, so judge the candidate's colours and tones "
               "relative to these frames, not against the nominal numbers in the brief. The reference is not "
               "what the brief asks for; it only shows how a known look renders here. Calibration: for a brief "
               "that described the reference look exactly, the reference frames would score 7 on every "
               "attribute; the scene's own limits (low-poly people, hard shadows, the straightness of the "
               "water's edge, the sun glint on wet sand) are not the candidate's defects unless the candidate "
               "makes them worse. Score above 7 where the candidate matches its brief better than the "
               "reference matches its own description, below 7 where it is worse or wrong.")


def judge(segment: str, brief: dict, frames: list, reference: list | None = None, log_ctx: dict | None = None) -> dict:
    rubric = read(PIPE / "rubrics" / f"{segment}.md")
    spec = SEGMENTS[segment]
    world = brief.get("world", spec["world"])
    labels = spec.get("views_by_world", {}).get(world) or spec.get("views") or \
        {"sky": ['default view', 'tilted up', 'side view']}.get(segment, ['default view', 'turned to one side', 'turned to the other side'])
    blocks = [{"text": "Brief:\n" + json.dumps({k: v for k, v in brief.items() if k != "id"}, indent=2)}]
    ref_desc = spec.get("reference", {}).get(world)
    if reference and ref_desc:
        # the shipped layer under the same views anchors the judge: how this scene's
        # lighting renders a colour (knob segments), how much of a block's furniture
        # the views actually show (street props)
        note = spec.get("reference_note", COLOUR_NOTE)
        if isinstance(note, dict):   # per-world notes (props: street furniture vs beach furniture)
            note = note.get(world, COLOUR_NOTE)
        blocks.append({"text": f"Reference frames: the shipped default layer under the same views ({ref_desc}). " + note})
        for i, f in enumerate(reference):
            blocks.append({"text": f"Reference {i + 1} ({labels[i] if i < len(labels) else 'extra'}):"})
            blocks.append(image_block(f))
        blocks.append({"text": "Candidate frames follow."})
    for i, f in enumerate(frames):
        blocks.append({"text": f"Frame {i + 1} ({labels[i] if i < len(labels) else 'extra'}):"})
        blocks.append(image_block(f))
    blocks.append({"text": "Score the candidate frames against the brief. JSON only."})
    image_paths = (list(reference) if reference and ref_desc else []) + list(frames)   # image block order, for the call log
    text2 = None
    # a segment's own judge wins over JUDGE_MODEL (orchestrators export Sonnet 5 for everything):
    # vegetation and props use Opus 5, chosen on Marc's anchor labels 2026-09-14
    model = spec.get("judge_model") or JUDGE_MODEL
    text, usage = converse(model, rubric, blocks, max_tokens=3000)
    try:
        j = parse_json(text)
    except Exception as e:
        # one repair round: the same judge, shown its own reply and the parse error
        blocks2 = blocks + [{"text": "Your previous reply could not be parsed as JSON (%s). Reply again with the "
                                     "same judgement as strictly valid JSON only, escaping quotes inside strings:\n%s" % (e, text[:6000])}]
        text2, usage2 = converse(model, rubric, blocks2, max_tokens=3000)
        usage = {k: usage.get(k, 0) + usage2.get(k, 0) for k in set(usage) | set(usage2)}
        try:
            j = parse_json(text2)
        except Exception:
            j = {"attributes": {}, "overall": 0, "pass": False, "revision_notes": "judge reply was not JSON: " + text2[:300]}
    if not isinstance(j, dict):
        j = {"attributes": {}, "overall": 0, "pass": False, "revision_notes": "judge reply was not a JSON object"}
    # judges sometimes give an attribute as a bare score ({"density": 6}) instead of {score, evidence}
    j["attributes"] = {k: (v if isinstance(v, dict) else {"score": v, "evidence": ""})
                       for k, v in (j.get("attributes") or {}).items()} if isinstance(j.get("attributes"), dict) else {}
    j["usage"] = usage
    try:   # full record for training a local judge later (calllog.py); never breaks verification
        from calllog import log_blocks, log_call
        log_call("judge", {"type": "call", **(log_ctx or {}), "segment": segment, "world": world, "model": model,
                           "system": rubric, "blocks": log_blocks(blocks, image_paths), "reply": text,
                           "repair_reply": text2, "has_reference": bool(reference and ref_desc),
                           "verdict": {k: v for k, v in j.items() if k != "usage"}, "usage": usage})
    except Exception as e:
        print(f"  calllog: judge call not logged ({str(e)[:160]})", flush=True)
    return j


# ------------------------------------------------------------- aggregate ---

def verify_one(row: dict, out_dir: Path, do_judge=True) -> dict:
    segment = row["segment"]
    brief = row["brief"]
    cid = row["candidate"]
    spec = SEGMENTS[segment]
    world = brief.get("world", spec["world"])
    code = read(row["path"])
    res = {"candidate": cid, "brief_id": brief["id"], "segment": segment, "brief": brief, "path": row["path"],
           "mode": row.get("mode", "write"), "prompt": row.get("prompt", ""), "gates": {}, "score": 0.0,
           "pass": False, "evidence": "", "checks": {}, "judge": {}}
    t0 = time.time()
    problems = static_gate(code, segment)
    res["gates"]["static"] = problems
    if problems:
        res["evidence"] = "static gate: " + "; ".join(problems)
        return res
    swap = f"{segment}:{install_candidate(segment, cid, code)}"
    ok, errors = runtime_gate(world, swap)
    res["gates"]["runtime"] = errors
    if not ok:
        res["evidence"] = "runtime gate: " + " | ".join(errors)
        return res
    cap_dir = out_dir / "captures" / cid
    script = spec.get("script_by_world", {}).get(world, spec["script"])
    try:
        with GPU_LOCK:
            base = baseline(world, spec["shots"], script, segment)
            stats = capture(world, swap, cap_dir, spec["shots"], script)
    except Exception as e:
        res["gates"]["capture"] = [str(e)[:300]]
        res["evidence"] = "capture failed: " + str(e)[:300]
        return res
    res["stats"] = {k: stats[k] for k in ("fps_avg", "draw_calls", "palette", "obstacles", "probe") if k in stats}
    res["frames"] = stats["frames"]
    cscore, notes = CHECKS[segment](brief, stats, base)
    res["checks"] = {"score": cscore, "notes": notes}
    jscore = None
    if do_judge:
        j = judge(segment, brief, stats["frames"], base.get("frames") if "reference" in spec else None,
                  log_ctx={"run": out_dir.name, "candidate": cid, "brief_id": brief["id"], "mode": row.get("mode", "write"), "brief": brief})
        res["judge"] = j
        jscore = float(j.get("overall", 0)) / 10.0
    if jscore is None:
        res["score"] = cscore
        res["pass"] = cscore >= 0.7
    else:
        res["score"] = 0.4 * cscore + 0.6 * jscore
        res["pass"] = judge_pass(segment, j) and cscore >= 0.6
    ev = checks_evidence(notes, cscore)
    if do_judge:
        for k, v in res["judge"].get("attributes", {}).items():
            ev.append(f"{k} {v.get('score')}/10: {v.get('evidence', '')}")
        if res["judge"].get("revision_notes"):
            ev.append("revise: " + res["judge"]["revision_notes"])
    res["evidence"] = "\n".join(ev)
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ------------------------------------------------------------- composite ---

def verify_composite(scene_brief: str, world: str, briefs: dict, accepted: dict, out_dir: Path,
                     run: str = "", round_: int = 0) -> dict:
    """The assembled scene: every accepted layer at once (segments not accepted keep the shipped layer),
    captured with the composite recipes and judged against the shipped scene with the whole-scene rubric.
    briefs: segment -> brief; accepted: segment -> res:// path. Returns pass, score, evidence, and the
    segments to blame (worst first) with the judge's per-segment problem and fix, for revision briefs."""
    spec = SEGMENTS["composite"]
    swap = ";".join(f"{s}:{p}" for s, p in accepted.items())
    cap_root = Path(out_dir) / "composite" / f"round{round_}"
    frames, ref_frames, added_dc, fps = [], [], 0, 999.0
    with GPU_LOCK:
        for i, rec in enumerate(spec["recipes"]):
            script = rec.get("script_by_world", {}).get(world, rec["script"])
            base = baseline(world, rec["shots"], script, f"composite{i}")
            stats = capture(world, swap, cap_root / f"view{i}", rec["shots"], script)
            frames += stats["frames"]
            ref_frames += base["frames"]
            added_dc = max(added_dc, stats["draw_calls"] - base["draw_calls"])
            fps = min(fps, stats["fps_avg"])
    # Scene-level draw calls are information only: two captures of the same shipped street under the two
    # recipes counted 81 and 681 (the total follows what is on screen at the capture moment), so a scene
    # delta is noise. Each layer's own check already enforces its budget; the scene check is the fps floor.
    cnotes = [f"fps {fps:.0f}",
              f"draw calls {added_dc:+d} vs the shipped scene (information only; replaced layers: {', '.join(accepted) or 'none'})"]
    cscore = 1.0
    if fps < 60:
        cscore = 0.3
        cnotes.append("below 60 fps")
    brief = {"id": f"composite-{run}-r{round_}", "segment": "composite", "world": world, "scene_brief": scene_brief,
             "segments": {s: {"brief": b.get("text", ""), "layer": "new (accepted)" if s in accepted else "shipped (not accepted)"}
                          for s, b in briefs.items()}}
    j = judge("composite", brief, frames, ref_frames,
              log_ctx={"run": run, "candidate": brief["id"], "brief_id": brief["id"], "mode": "composite", "brief": brief})
    segs = j.get("segments") if isinstance(j.get("segments"), dict) else {}
    passed = bool(j.get("pass")) and cscore >= 0.6
    notes = {}
    for s, v in segs.items():
        if isinstance(v, dict):
            sc = v.get("score")
            notes[s] = {"score": sc if isinstance(sc, (int, float)) else None,
                        "problem": str(v.get("problem") or ""), "revise": str(v.get("revise") or "")}
    blame = sorted((s for s, v in notes.items() if v["score"] is not None and
                    (v["score"] < 6 or (not passed and v["score"] < 7 and v["revise"]))),
                   key=lambda s: notes[s]["score"])
    ev = checks_evidence(cnotes, cscore)
    ev += [f"{k} {v.get('score')}/10: {v.get('evidence', '')}" for k, v in j.get("attributes", {}).items()]
    ev += [f"segment {s} {v['score']}/10: {v['problem']}" + (f" | fix: {v['revise']}" if v["revise"] else "") for s, v in notes.items()]
    if j.get("revision_notes"):
        ev.append("scene: " + j["revision_notes"])
    return {"pass": passed, "score": 0.4 * cscore + 0.6 * float(j.get("overall") or 0) / 10.0, "evidence": "\n".join(ev),
            "blame": blame, "segment_notes": notes, "judge": j, "checks": {"score": cscore, "notes": cnotes},
            "frames": frames, "reference_frames": ref_frames, "swap": swap}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", help="candidates.jsonl / revisions.jsonl from teacher.py")
    ap.add_argument("--file", help="verify one layer file")
    ap.add_argument("--segment", default="sky")
    ap.add_argument("--brief", help="brief JSON (with --file)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--name", default="verified.jsonl")
    ap.add_argument("--workers", type=int, default=3, help="candidates in flight (captures are still one at a time)")
    ap.add_argument("--resume", action="store_true", help="skip candidates already in the output file")
    ap.add_argument("--rescore", action="store_true", help="recompute checks and pass from saved captures + judge (no GPU, no Bedrock); re-verify rows without them")
    ap.add_argument("--rejudge-world", help="with --rescore: fully re-verify (capture + judge) rows of this world, e.g. after a recipe change")
    ap.add_argument("--rejudge-saved", help="with --rescore: judge rows of this world again from their saved frames (new judge prompt, no capture)")
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if a.file:
        brief = json.loads(a.brief) if a.brief else {"id": "adhoc", "segment": a.segment, "world": SEGMENTS[a.segment]["world"]}
        rows = [{"candidate": Path(a.file).stem, "segment": a.segment, "brief": brief, "path": a.file}]
    else:
        rows = read_jsonl(a.candidates)
    results = []
    done = 0
    lock = threading.Lock()

    already = {}
    if a.rescore and (out_dir / a.name).exists():
        def finish(r0, stats, base, j):
            cscore, notes = CHECKS[r0["segment"]](r0["brief"], stats, base)
            r0["judge"] = j
            r0["checks"] = {"score": cscore, "notes": notes}
            r0["stats"] = {k: stats[k] for k in ("fps_avg", "draw_calls", "palette", "obstacles", "probe") if k in stats}
            r0["score"] = 0.4 * cscore + 0.6 * float(j.get("overall", 0)) / 10.0
            r0["pass"] = judge_pass(r0["segment"], j) and cscore >= 0.6
            ev = checks_evidence(notes, cscore) + [f"{k} {v.get('score')}/10: {v.get('evidence', '')}" for k, v in j.get("attributes", {}).items()]
            if j.get("revision_notes"):
                ev.append("revise: " + j["revision_notes"])
            r0["evidence"] = "\n".join(ev)
            already[r0["candidate"]] = r0

        pending = []
        for r0 in read_jsonl(out_dir / a.name):
            cap = out_dir / "captures" / r0["candidate"] / "stats.json"
            if r0.get("judge") and cap.exists():
                stats = json.loads(cap.read_text())
                stats["frames"] = sorted(str(p) for p in cap.parent.glob("*_*s.png"))
                spec = SEGMENTS[r0["segment"]]
                world = r0["brief"].get("world", spec["world"])
                if a.rejudge_world and world == a.rejudge_world:
                    continue   # re-verified in full (new capture recipe)
                with GPU_LOCK:
                    base = baseline(world, spec["shots"], spec.get("script_by_world", {}).get(world, spec["script"]), r0["segment"])
                if a.rejudge_saved and world == a.rejudge_saved:
                    pending.append((r0, stats, base))   # new judge prompt, same frames
                    continue
                finish(r0, stats, base, r0["judge"])
            elif a.rejudge_saved:
                # a new judge prompt changes nothing for rows that never reached the judge:
                # keep them rather than rerun their gates (Godot processes, memory)
                already[r0["candidate"]] = r0
            elif r0["gates"].get("static") and any("must start with" in x for x in r0["gates"]["static"]):
                # a nested code fence hid the extends line: strip fence lines and re-verify
                p = Path(r0["path"])
                p.write_text("\n".join(l for l in p.read_text().splitlines() if not l.strip().startswith("```")) + "\n")
        if pending:
            print(f"rejudge: {len(pending)} {a.rejudge_saved} rows from their saved frames", flush=True)

            def rejudge(p):
                r0, stats, base = p
                spec = SEGMENTS[r0["segment"]]
                try:
                    j = judge(r0["segment"], r0["brief"], stats["frames"], base.get("frames") if "reference" in spec else None,
                              log_ctx={"run": out_dir.name, "candidate": r0["candidate"], "brief_id": r0.get("brief_id"),
                                       "mode": "rejudge", "brief": r0["brief"]})
                except Exception as e:   # keep the old judgement rather than lose the row
                    print(f"  {r0['candidate']}: rejudge failed ({str(e)[:120]}), kept the old judgement", flush=True)
                    j = r0["judge"]
                finish(r0, stats, base, j)
                print(f"  {r0['candidate']}: {'PASS' if r0['pass'] else 'fail'} judge {j.get('overall', '-')}", flush=True)

            with ThreadPoolExecutor(max(1, a.workers)) as ex:
                list(ex.map(rejudge, pending))
        results.extend(already.values())
        # --candidates may be the run's briefs rather than candidate rows (they carry no "candidate"
        # key): a re-judge still has everything it needs from disk, so keep going instead of losing
        # the work at the last line, as a sky re-judge did on Sep 15 after paying for 30 judge calls
        rows = [r0 for r0 in rows if r0.get("candidate") not in already and "candidate" in r0]
        print(f"rescore: {len(already)} rescored from disk, {len(rows)} to re-verify", flush=True)
    if a.resume and (out_dir / a.name).exists():
        for r0 in read_jsonl(out_dir / a.name):
            already[r0["candidate"]] = r0
        results.extend(already.values())
        rows = [r0 for r0 in rows if r0["candidate"] not in already]
        print(f"resume: {len(already)} already verified, {len(rows)} to go")

    def work(row):
        nonlocal done
        try:
            r = verify_one(row, out_dir, do_judge=not a.no_judge)
        except subprocess.TimeoutExpired as e:
            r = {"candidate": row["candidate"], "brief_id": row["brief"]["id"], "segment": row["segment"], "brief": row["brief"],
                 "path": row["path"], "mode": row.get("mode", "write"), "prompt": row.get("prompt", ""),
                 "gates": {"runtime": ["timed out: the scene never finished building (an endless loop?)"]},
                 "score": 0.0, "pass": False, "evidence": "runtime gate: timed out after %ss; the scene never finished building" % e.timeout,
                 "checks": {}, "judge": {}}
        except Exception as e:   # never let one candidate take the run down
            r = {"candidate": row["candidate"], "brief_id": row["brief"]["id"], "segment": row["segment"], "brief": row["brief"],
                 "path": row["path"], "mode": row.get("mode", "write"), "prompt": row.get("prompt", ""),
                 "gates": {"capture": [str(e)[:300]]}, "score": 0.0, "pass": False,
                 "evidence": "verifier error: " + str(e)[:300], "checks": {}, "judge": {}}
        with lock:
            done += 1
            results.append(r)
            j = r.get("judge", {})
            print(f"[{done}/{len(rows)}] {r['candidate']}: {'PASS' if r['pass'] else 'fail'} score {r['score']:.2f} "
                  f"checks {r['checks'].get('score', 0):.2f} judge {j.get('overall', '-')} ({r.get('seconds', 0)}s)", flush=True)
            if not r["pass"]:
                print("      " + r["evidence"].splitlines()[0][:160], flush=True)
            if done % 10 == 0:
                write_jsonl(out_dir / a.name, results)   # checkpoint
        return r

    with ThreadPoolExecutor(max(1, a.workers)) as ex:
        list(ex.map(work, rows))
    results.sort(key=lambda r: r["candidate"])
    write_jsonl(out_dir / a.name, results)
    n_pass = sum(1 for r in results if r["pass"])
    print(f"{n_pass}/{len(results)} passed -> {out_dir / a.name}")


if __name__ == "__main__":
    main()
