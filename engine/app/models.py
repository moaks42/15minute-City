"""Request models (mirror contracts/openapi.yaml). Responses are plain dicts validated in tests against the contract."""
from __future__ import annotations

import base64
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["pl", "cs", "en", "ko"]
Mode = Literal["transit", "bike", "walk"]


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Anchor(_M):
    id: str
    label: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    mode: Mode = "transit"
    level: int = Field(default=3, ge=1, le=5)
    maxMinutes: int | None = Field(default=None, ge=1, le=120)


class MustHave(_M):
    category: str
    maxWalkMin: float = Field(ge=1, le=60)


class Filters(_M):
    maxPricePerM2: float | None = None
    maxRentPerM2: float | None = None
    maxCommuteMinutes: int | None = Field(default=None, ge=1, le=120)
    mustHave: list[MustHave] = Field(default_factory=list)
    maxNoiseDb: float | None = None


class Budget(_M):
    total: float | None = Field(default=None, gt=0)
    monthlyRent: float | None = Field(default=None, gt=0)


class ScoreRequest(_M):
    v: int = 1
    lang: Lang | None = None
    persona: str | None = None
    weights: dict[str, int] = Field(default_factory=dict)
    indicatorWeights: dict[str, float] = Field(default_factory=dict)
    anchors: list[Anchor] = Field(default_factory=list, max_length=3)
    filters: Filters = Field(default_factory=Filters)
    budget: Budget = Field(default_factory=Budget)
    aggregate: Literal["hex", "district", "neighborhood"] = "hex"
    limit: int = Field(default=20, ge=1, le=100)
    includeCells: bool = True
    rankBy: str | None = None      # None = match %, a criterion id, or "anchor:<id>" (shortest travel time)
    district: str | None = None    # aggregate=hex: only cells of this district


class PrefChoice(_M):
    a: dict[str, float]
    b: dict[str, float]
    choice: Literal["a", "b"]


class PrefFitRequest(_M):
    choices: list[PrefChoice] = Field(min_length=1)


def decode_state(state: str | None) -> ScoreRequest | None:
    """`state` = base64url(JSON ScoreRequest), padding optional."""
    if not state:
        return None
    pad = "=" * (-len(state) % 4)
    data = json.loads(base64.urlsafe_b64decode(state + pad).decode("utf-8"))
    return ScoreRequest.model_validate(data)


def encode_state(req: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(req).encode("utf-8")).decode("ascii").rstrip("=")
