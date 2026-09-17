"""Held-out fauna-layer brief sampler (segment 6: the Herd).

Conditions the ANIMALS — species, build, group behaviour, gait — while the contract
fixes where they live (the home meadow) and how they react to the host states
(ctx.cur.herdMood / herdSpeed). Seeded so eval/train/CaR/RL sets are disjoint by seed.
"""
from __future__ import annotations

import random

SPECIES = [
    "wild horses with long manes and tails",
    "bison with heavy humped shoulders and short horns",
    "elk with tall branching antlers on the bulls",
    "pronghorn with slim legs and pale rumps",
    "highland cattle with shaggy coats and wide horns",
]
GROUP = [
    "a loose family band of 6-8 with one larger lead animal",
    "a tight cluster of 5 that moves as one",
    "a scattered group of 8-10 spread across the meadow",
    "a small group of 4 with a lookout that stands apart",
]
BEHAVIOUR = [
    "grazing with heads down, occasionally looking up",
    "slowly drifting across the meadow while grazing",
    "restless, often pausing alert with heads raised",
    "calm, some lying low while others graze",
]
GAIT = [
    "a stiff four-beat walk",
    "a bouncy trot when moving",
    "a heavy lumbering walk",
    "a light springy step",
]
MOODS = ["pastoral", "wild", "watchful", "peaceful", "ancient", "skittish", "noble"]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{
        "id": f"fauna-{i:03d}",
        "species": rng.choice(SPECIES),
        "group": rng.choice(GROUP),
        "behaviour": rng.choice(BEHAVIOUR),
        "gait": rng.choice(GAIT),
        "mood": ", ".join(rng.sample(MOODS, 2)),
    } for i in range(n)]


def brief_text(b: dict) -> str:
    return (f"Animals: {b['species']}. Group: {b['group']}. Behaviour: {b['behaviour']}. "
            f"Gait: {b['gait']}. Mood: {b['mood']}.")
