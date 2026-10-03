"""Local geocoder index (README §4 `geocode`): addresses, streets, neighbourhoods, districts → geocode.parquet.

Columns: label, sublabel (district name), kind (address|street|place|district), lat, lon, h3, search
`search` is lower-case, diacritics-free (ł→l), so "zizkov" finds "Žižkov" and "rakowicka" finds "Rakowicka".
POIs are not repeated here; the engine already has pois.parquet.
"""
from __future__ import annotations

import re
import unicodedata

import geopandas as gpd
import h3
import numpy as np
import pandas as pd


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower().replace("ł", "l"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/.-]", " ", s)).strip()


def build(addr: gpd.GeoDataFrame, grid: pd.DataFrame, districts: gpd.GeoDataFrame,
          neighborhoods: gpd.GeoDataFrame | None) -> pd.DataFrame:
    a = addr.to_crs(4326)
    lat, lon = a.geometry.y.to_numpy(), a.geometry.x.to_numpy()
    cells = np.array([h3.latlng_to_cell(y, x, 9) for y, x in zip(lat, lon)])
    dist = grid.set_index("h3")["district_name"]
    sub = pd.Series(cells).map(dist).fillna("").to_numpy()
    rows = [pd.DataFrame({"label": a["label"].to_numpy(), "sublabel": sub, "kind": "address", "lat": lat, "lon": lon,
                          "h3": cells, "search": a["search"].to_numpy()})]
    # streets: median point of their addresses
    st = pd.DataFrame({"street": a["street"].to_numpy(), "lat": lat, "lon": lon, "sub": sub})
    st = st[st["street"].fillna("").str.len() > 0]
    sg = st.groupby("street").agg(lat=("lat", "median"), lon=("lon", "median"),
                                  sub=("sub", lambda s: s.value_counts().index[0])).reset_index()
    sg["h3"] = [h3.latlng_to_cell(y, x, 9) for y, x in zip(sg["lat"], sg["lon"])]
    rows.append(pd.DataFrame({"label": sg["street"], "sublabel": sg["sub"], "kind": "street", "lat": sg["lat"],
                              "lon": sg["lon"], "h3": sg["h3"], "search": sg["street"].map(fold)}))
    for g, kind in ((neighborhoods, "place"), (districts, "district")):
        if g is None or g.empty:
            continue
        g = g.to_crs(4326)
        p = g.geometry.representative_point()
        c = [h3.latlng_to_cell(y, x, 9) for y, x in zip(p.y, p.x)]
        rows.append(pd.DataFrame({"label": g["name"].astype(str).to_numpy(),
                                  "sublabel": pd.Series(c).map(dist).fillna("").to_numpy() if kind == "place" else "",
                                  "kind": kind, "lat": p.y.round(6).to_numpy(), "lon": p.x.round(6).to_numpy(),
                                  "h3": c, "search": g["name"].astype(str).map(fold).to_numpy()}))
    out = pd.concat(rows, ignore_index=True)
    out["lat"], out["lon"] = out["lat"].astype(float).round(6), out["lon"].astype(float).round(6)
    for c in ("label", "sublabel", "kind", "h3", "search"):
        out[c] = out[c].astype("string")
    return out.drop_duplicates(["kind", "label", "h3"]).reset_index(drop=True)
