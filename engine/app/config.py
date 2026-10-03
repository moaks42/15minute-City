"""Settings + config/*.yaml → typed specs. City differences come only from config/cities/*.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = ENGINE_DIR.parent
LANGS = ("pl", "cs", "en")
CITIES = ("krakow", "praha")


@dataclass(frozen=True)
class Settings:
    config_dir: Path
    data_dir: Path
    devdata_dir: Path
    models_dir: Path
    export_dir: Path
    cors_origins: tuple[str, ...]
    golemio_api_key: str | None
    data_fallback: str  # "synthetic" → use dev data when real data is missing or invalid; "none" → fail loudly
    offline: bool       # tests: no outbound HTTP (live air, Photon)


def _path(env: str, default: Path) -> Path:
    v = os.environ.get(env)
    return Path(v).resolve() if v else default


@lru_cache
def settings() -> Settings:
    return Settings(
        config_dir=_path("CONFIG_DIR", REPO_DIR / "config"),
        data_dir=_path("DATA_DIR", REPO_DIR / "data" / "processed"),
        devdata_dir=_path("DEVDATA_DIR", ENGINE_DIR / ".devdata"),
        models_dir=_path("MODELS_DIR", ENGINE_DIR / "models"),
        export_dir=_path("EXPORT_DIR", ENGINE_DIR / "export"),
        cors_origins=tuple(o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()),
        golemio_api_key=os.environ.get("GOLEMIO_API_KEY") or None,
        data_fallback=os.environ.get("DATA_FALLBACK", "synthetic"),
        offline=os.environ.get("KOMPAS_OFFLINE", "0") == "1",
    )


@dataclass(frozen=True)
class IndicatorSpec:
    key: str          # "<criterion>.<indicator>" — persona overrides use this
    criterion: str
    id: str
    column: str       # features.parquet column (== key unless the yaml aliases it)
    label: dict
    unit: str
    decimals: int
    norm: dict
    weight: float
    walk_scaled: bool
    cross_city: bool
    no_warning: bool
    priority: str
    cities: tuple[str, ...] | None
    sources: dict
    explain: dict

    @property
    def is_alias(self) -> bool:
        return self.column != self.key

    def applies_to(self, city: str) -> bool:
        return self.cities is None or city in self.cities


@dataclass
class Config:
    raw: dict
    cities: dict[str, dict]
    indicators: dict[str, list[IndicatorSpec]] = field(default_factory=dict)  # city → specs (overrides applied)

    @property
    def criteria(self) -> list[dict]:
        return self.raw["criteria"]

    @property
    def criterion_ids(self) -> list[str]:
        return [c["id"] for c in self.raw["criteria"]]

    def level_weight(self, level: int) -> float:
        return float(self.raw["levels"][int(level)])

    def persona(self, pid: str | None) -> dict:
        for p in self.raw["personas"]:
            if p["id"] == (pid or "custom"):
                return p
        return next(p for p in self.raw["personas"] if p["id"] == "custom")

    def must_have(self, cat: str) -> dict | None:
        return next((m for m in self.raw["mustHaveCategories"] if m["id"] == cat), None)

    def text(self, *path: str) -> dict:
        node = self.raw["texts"]
        for p in path:
            node = node[p]
        return node


def _spec(crit: dict, ind: dict, override: dict) -> IndicatorSpec:
    key = f"{crit['id']}.{ind['id']}"
    return IndicatorSpec(
        key=key, criterion=crit["id"], id=ind["id"], column=ind.get("column", key),
        label=override.get("label", ind["label"]), unit=ind["unit"], decimals=int(ind.get("decimals", 0)),
        norm=dict(ind["norm"]), weight=float(ind["weight"]), walk_scaled=bool(ind.get("walkScaled", False)),
        cross_city=bool(ind.get("crossCity", False)), no_warning=bool(ind.get("noWarning", False)),
        priority=ind.get("priority", "P1"), cities=tuple(ind["cities"]) if ind.get("cities") else None,
        sources=ind.get("sources", {}), explain=override.get("explain", ind["explain"]),
    )


def load_config(config_dir: Path | None = None) -> Config:
    d = config_dir or settings().config_dir
    raw = yaml.safe_load((d / "indicators.yaml").read_text(encoding="utf-8"))
    cities = {}
    for p in sorted((d / "cities").glob("*.yaml")):
        cc = yaml.safe_load(p.read_text(encoding="utf-8"))
        cities[cc["id"]] = cc
    cfg = Config(raw=raw, cities=cities)
    for cid, cc in cities.items():
        ov = cc.get("indicatorOverrides", {}) or {}
        cfg.indicators[cid] = [
            _spec(crit, ind, ov.get(f"{crit['id']}.{ind['id']}", {}))
            for crit in raw["criteria"] for ind in crit.get("indicators", [])
        ]
    return cfg
