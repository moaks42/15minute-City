"""Per-city build context passed to core steps and city adapters."""
from __future__ import annotations

from dataclasses import dataclass, field

import geopandas as gpd
import numpy as np
import pandas as pd

from .common import Manifest, raw_dir, settings


@dataclass
class Ctx:
    city: str
    s: dict = field(default_factory=dict)
    man: Manifest | None = None
    grid: gpd.GeoDataFrame | None = None  # h3, lat, lon, geometry (+ labels)
    xy: np.ndarray | None = None  # cell centroids in metric CRS
    pois: pd.DataFrame | None = None
    stops: pd.DataFrame | None = None
    graph: object | None = None
    districts: gpd.GeoDataFrame | None = None
    boundary: gpd.GeoDataFrame | None = None
    service_date: str | None = None
    addresses: gpd.GeoDataFrame | None = None

    @classmethod
    def make(cls, city: str) -> "Ctx":
        return cls(city=city, s=settings(city), man=Manifest(city))

    @property
    def crs(self) -> str:
        return self.s["metricCrs"]

    @property
    def raw(self):
        return raw_dir(self.city)

    def src(self, key: str) -> dict:
        return next(x for x in self.s["sources"] if x["key"] == key)

    def raw_file(self, key: str):
        return self.raw / self.src(key)["file"]

    def ok(self, key: str, rows: int | None, note: str = "", status: str = "ok") -> None:
        self.man.record(key, rows=rows, status=status, note=note)

    def missing(self, key: str, note: str) -> None:
        self.man.record(key, rows=0, status="missing", note=note)
