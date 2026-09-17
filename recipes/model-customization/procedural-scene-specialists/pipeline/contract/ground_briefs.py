"""Held-out ground-layer brief sampler (segment 2: the Prairie terrain).

A ground brief conditions the TECHNIQUE of the turf surface — texture variation,
soil exposure, wetness, detail scale — not the per-state palette (uGrassA/B and
the lighting come from the host's uniforms) and never the height (groundH is
frozen). Seeded so eval/train/CaR/RL sets are reproducible and disjoint by seed.
"""
from __future__ import annotations

import random

TURF = [
    "short grazed turf with fine, even texture",
    "tall uneven bunchgrass tussocks with clumpy variation",
    "a patchwork of green and sun-bleached straw-colored grass",
    "lush wet meadow turf, darker and saturated in the hollows",
    "sparse dry steppe grass over pale earth",
    "rolling turf with long wind-combed streaks",
]
SOIL = [
    "no visible soil",
    "small bare dirt patches scattered across the basin",
    "a worn game trail of packed earth winding through",
    "exposed gravel on the higher ridges",
    "dark muddy soil pooling in the low ground",
]
EXTRAS = [
    "cloud shadows clearly legible as they cross the ground",
    "the crepuscular light corridor visibly brightening the turf",
    "subtle large-scale mottling so it never looks tiled",
    "fine detail up close fading to smooth color with distance",
    "a slight sheen on the grass toward the sun",
    "moisture darkening in the hollows",
]
MOODS = [
    "pastoral", "windswept", "arid", "fertile", "quiet", "rugged",
    "golden", "cold", "lush", "weathered", "open", "tender",
]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{
        "id": f"ground-{i:03d}",
        "turf": rng.choice(TURF),
        "soil": rng.choice(SOIL),
        "extras": rng.sample(EXTRAS, rng.randint(0, 2)),
        "mood": ", ".join(rng.sample(MOODS, rng.randint(2, 3))),
    } for i in range(n)]


def brief_text(b: dict) -> str:
    parts = [f"Turf: {b['turf']}.", f"Soil: {b['soil']}."]
    if b["extras"]:
        parts.append("Also: " + "; ".join(b["extras"]) + ".")
    parts.append(f"Mood: {b['mood']}.")
    return " ".join(parts)
