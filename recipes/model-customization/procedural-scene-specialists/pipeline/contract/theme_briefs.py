"""Seeded scene-theme sampler for the director's planner (Phase 4).

A theme is the one sentence a person would say to ask for a scene ("a storm breaking over the high prairie as a bison herd
bunches and runs"). The planner turns it into one brief per segment. Seeded like the per-segment brief samplers, so the
planner's training themes (seed 2) and held-out themes (seed 1) are reproducible and disjoint.
"""
from __future__ import annotations

import random

# time-of-day lives in TIME only: a weather phrase that also names a time ("a bright windy afternoon") produces
# self-contradictory themes like "a bright windy afternoon … in the blue hour before sunrise"
WEATHER = [
    "a storm breaking", "a hushed mist settling", "bright gusting wind", "a cold grey overcast",
    "the first clear light after rain", "a still, heavy, thundery calm", "thin high cloud and hard sun",
    "a dry haze dulling the distance", "gusting squalls crossing the basin", "a soft warm glow",
]
TIME = [
    "at first light", "in the late afternoon", "at midday", "toward dusk",
    "in the blue hour before sunrise", "under a high noon sun",
]
ANIMALS = [
    "a bison herd", "a band of elk", "wild horses", "a scattered group of deer",
    "a single old bull apart from the herd", "a nursery group with young close by",
]
EVENT = [
    "bunching and running for shelter", "grazing quietly in the hollows", "crossing the open meadow",
    "drifting slowly downwind", "standing alert, heads raised", "picking through sparse grazed turf",
    "moving in single file along a game trail", "settling to rest as the light goes",
]
MOODS = [
    "urgent", "hushed", "vast", "tender", "austere", "restless", "luminous", "brooding",
    "pastoral", "cold", "golden", "windswept",
]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{
        "id": f"theme-{i:03d}",
        "weather": rng.choice(WEATHER),
        "time": rng.choice(TIME),
        "animals": rng.choice(ANIMALS),
        "event": rng.choice(EVENT),
        "mood": ", ".join(rng.sample(MOODS, 2)),
    } for i in range(n)]


def brief_text(t: dict) -> str:
    return f"{t['weather']} over the high prairie {t['time']}, with {t['animals']} {t['event']}. Mood: {t['mood']}."
