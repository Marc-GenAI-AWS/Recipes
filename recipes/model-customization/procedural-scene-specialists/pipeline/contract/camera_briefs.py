"""Held-out camera-layer brief sampler (segment 3: the CameraRig).

A camera brief conditions the SHOT — movement style, framing, pace — not the scene
content. The rig must stay above the frozen groundH, inside the basin, and keep the
sky/peaks/basin readable. Seeded so eval/train/CaR/RL sets are disjoint by seed.
"""
from __future__ import annotations

import random

MOVES = [
    "a slow lateral dolly along the southern knoll",
    "a gentle half-orbit around the grazing herd",
    "a low grass-level push-in toward the saddle",
    "a high overlook that drifts slowly down toward the basin",
    "a near-static tripod shot with a slow but visible drift",
    "a slow crane rise revealing the peaks behind the herd",
]
FRAMING = [
    "rule of thirds with the saddle on the upper third",
    "the herd in the lower-left foreground, peaks behind",
    "a wide establishing frame of the whole basin",
    "a symmetric composition centered on the saddle gap",
    "foreground grass framing the bottom edge, deep space beyond",
]
# every pace must still read as motion within the verifier's 4 s animation window
# ("barely perceptible" failed the animates gate in the Fable smoke, 2026-09-14)
PACE = ["very slow and meditative", "unhurried", "slow but alive", "steady and deliberate"]
MOODS = ["contemplative", "epic", "intimate", "serene", "watchful", "vast", "tender", "stately"]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{
        "id": f"camera-{i:03d}",
        "move": rng.choice(MOVES),
        "framing": rng.choice(FRAMING),
        "pace": rng.choice(PACE),
        "mood": ", ".join(rng.sample(MOODS, 2)),
    } for i in range(n)]


def brief_text(b: dict) -> str:
    return (f"Move: {b['move']}. Framing: {b['framing']}. Pace: {b['pace']}. "
            f"Mood: {b['mood']}.")
