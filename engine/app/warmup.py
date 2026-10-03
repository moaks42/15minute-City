"""Build-time warm-up (Dockerfile): load both cities (generating synthetic dev data if real data is absent),
train/load the archetype model into engine/models and write the static fallback export."""
from __future__ import annotations

import logging

from . import ml
from .config import load_config
from .data import load_all
from .export import export_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    cfg = load_config()
    cities = load_all(cfg)
    ml.load_or_train(cities, cfg)
    for p in export_all(cities=cities, cfg=cfg):
        print("export", p)
