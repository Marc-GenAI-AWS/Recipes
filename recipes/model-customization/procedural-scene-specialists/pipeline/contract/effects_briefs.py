"""Held-out effects-layer brief sampler (segment 5: the dawn Mist).

Conditions the mist's CHARACTER — form, texture, motion, light response — while the
contract fixes WHEN it shows (alpha × uMist, driven by the host states) and roughly
where (the basin hollows in front of the camera). Seeded so eval/train/CaR/RL sets
are disjoint by seed.
"""
from __future__ import annotations

import random

FORM = [
    "long thin ribbons threading along the creek hollows",
    "a broad soft blanket pooled across the low basin",
    "broken patchy wisps with clear gaps between",
    "stacked layers of low fog at different depths",
    "rolling banks that thicken toward the far basin",
]
TEXTURE = [
    "silky and smooth",
    "billowing with soft lumpy detail",
    "fine streaky filaments",
    "grainy, uneven density",
]
MOTION = [
    "drifting slowly east with the breeze",
    "almost still, gently breathing",
    "curling and slowly churning in place",
    "sliding downhill into the hollows",
]
LIGHT = [
    "glowing where the dawn light corridor cuts through",
    "cool blue-grey in shadow",
    "warm pink-lit on its upper edge",
    "evenly lit, pale and milky",
]
MOODS = ["hushed", "dreamlike", "cold", "mysterious", "tender", "primeval", "serene"]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{
        "id": f"effects-{i:03d}",
        "form": rng.choice(FORM),
        "texture": rng.choice(TEXTURE),
        "motion": rng.choice(MOTION),
        "light": rng.choice(LIGHT),
        "mood": ", ".join(rng.sample(MOODS, 2)),
    } for i in range(n)]


def brief_text(b: dict) -> str:
    return (f"Mist: {b['form']}, {b['texture']}. Motion: {b['motion']}. Light: {b['light']}. "
            f"Mood: {b['mood']}.")
