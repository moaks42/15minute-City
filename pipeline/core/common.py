"""Paths, settings, logging and the per-city manifest shared by all pipeline steps."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

PIPELINE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PIPELINE_DIR.parent
DATA_DIR = REPO_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INTERIM_DIR = DATA_DIR / "interim"  # gitignored scratch (clipped PBFs, graphs, r5 caches)
CONFIG_DIR = REPO_DIR / "config"

USER_AGENT = "Kompas-HackYeah2026/0.1 (data pipeline; github.com/moaks42/15minute-City)"

log = logging.getLogger("kompas")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_env() -> None:
    """Load KEY=VALUE lines from the repo .env into os.environ (no override)."""
    env = REPO_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def settings(city: str) -> dict:
    s = yaml.safe_load((PIPELINE_DIR / "settings" / f"{city}.yaml").read_text())
    shared = CONFIG_DIR / "cities" / f"{city}.yaml"
    if shared.exists():  # B's product config wins for shared keys (metricCrs, habitableMinAddresses, ...)
        cfg = yaml.safe_load(shared.read_text()) or {}
        for k in ("metricCrs", "habitableMinAddresses", "routingBufferKm"):
            if k in cfg:
                s[k] = cfg[k]
        s["_shared"] = cfg
    return s


def raw_dir(city: str) -> Path:
    p = RAW_DIR / city
    p.mkdir(parents=True, exist_ok=True)
    return p


def out_dir(city: str) -> Path:
    p = PROCESSED_DIR / city
    p.mkdir(parents=True, exist_ok=True)
    return p


def interim_dir(city: str) -> Path:
    p = INTERIM_DIR / city
    p.mkdir(parents=True, exist_ok=True)
    return p


class Manifest:
    """data/processed/{city}/manifest.json — one entry per source key (README §4 data rules)."""

    def __init__(self, city: str):
        self.city = city
        self.path = out_dir(city) / "manifest.json"
        self.data = {"city": city, "updatedAt": now_iso(), "sources": []}
        if self.path.exists():
            self.data = json.loads(self.path.read_text())

    def _find(self, key: str) -> dict | None:
        return next((e for e in self.data["sources"] if e["key"] == key), None)

    def record(self, key: str, **fields) -> dict:
        e = self._find(key)
        if e is None:
            e = {"key": key, "url": None, "fetchedAt": None, "licence": None, "rows": None,
                 "status": "missing", "note": ""}
            self.data["sources"].append(e)
        for k, v in fields.items():
            if v is not None or k in ("rows",):
                e[k] = v
        return e

    def get(self, key: str) -> dict | None:
        return self._find(key)

    def save(self) -> None:
        self.data["updatedAt"] = now_iso()
        self.data["sources"].sort(key=lambda e: e["key"])
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")
