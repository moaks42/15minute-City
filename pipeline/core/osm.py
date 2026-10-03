"""OSM: clip the regional PBF to city + routing buffer, export POIs / highways / landuse with osmium-tool."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .common import interim_dir, log, raw_dir, settings


def _run(cmd: list[str]) -> None:
    log.info("$ %s", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def clip(city: str, boundary: gpd.GeoDataFrame, force: bool = False) -> Path:
    """Clip the regional PBF to the city boundary buffered by routingBufferKm."""
    s = settings(city)
    out = interim_dir(city) / "clip.osm.pbf"
    if out.exists() and not force:
        return out
    buf = boundary.to_crs(s["metricCrs"]).buffer(s["routingBufferKm"] * 1000).to_crs(4326)
    poly = interim_dir(city) / "clip_polygon.geojson"
    poly.write_text(gpd.GeoSeries([buf.union_all()], crs=4326).to_json())
    _run(["osmium", "extract", "-p", poly, raw_dir(city) / s["osmPbf"], "-o", out, "--overwrite",
          "-s", "smart"])
    return out


def export(city: str, name: str, filters: list[str], geom_types: str = "point,linestring,polygon",
           force: bool = False) -> gpd.GeoDataFrame:
    """osmium tags-filter + export to GeoJSONSeq, read back as a GeoDataFrame (EPSG:4326)."""
    idir = interim_dir(city)
    pbf = idir / f"{name}.osm.pbf"
    seq = idir / f"{name}.geojsonseq"
    if force or not seq.exists():
        _run(["osmium", "tags-filter", idir / "clip.osm.pbf", *filters, "-o", pbf, "--overwrite"])
        cfg = idir / "export_config.json"
        cfg.write_text(json.dumps({"attributes": {"type": True, "id": True}, "linear_tags": True,
                                   "area_tags": True, "exclude_tags": [], "include_tags": []}))
        _run(["osmium", "export", pbf, "-f", "geojsonseq", "-o", seq, "--overwrite", "-c", cfg,
              f"--geometry-types={geom_types}"])
    gdf = gpd.read_file(seq, engine="pyogrio")
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    gdf = gdf.rename(columns={"@type": "osm_type", "@id": "osm_id"})
    log.info("[%s] osm export %s: %d features", city, name, len(gdf))
    return gdf


def col(gdf: pd.DataFrame, name: str) -> pd.Series:
    """Tag column or an all-None series if the tag never occurs."""
    if name in gdf.columns:
        return gdf[name]
    return pd.Series([None] * len(gdf), index=gdf.index, dtype=object)
