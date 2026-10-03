"""Local accent-insensitive search ("zizkov" → "Žižkov", "rakowicka" → "Rakowicka") + Photon fallback."""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass

import h3
import httpx
import pyarrow.parquet as pq
from cachetools import TTLCache

from .config import settings
from .data import CityData

log = logging.getLogger("kompas.geocode")
UA = {"User-Agent": "Kompas/0.1 (HackYeah 2026 demo; contact via GitHub moaks42/15minute-City)"}
_EXTRA = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "ß": "ss"})
KIND_BOOST = {"district": 30, "place": 25, "poi": 10, "address": 0}
_photon_cache: TTLCache = TTLCache(maxsize=512, ttl=3600)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.translate(_EXTRA))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    for ch in "-–,./()\"'„”":
        s = s.replace(ch, " ")
    return " ".join(s.split())


@dataclass
class Entry:
    label: str
    sublabel: str | None
    kind: str
    category: str | None
    lat: float
    lon: float
    folded: str
    tokens: tuple[str, ...]


class GeoIndex:
    def __init__(self, cd: CityData):
        self.cd = cd
        self.entries: list[Entry] = []
        self.prefix: dict[str, list[int]] = {}
        for g in cd.districts.values():
            self._add(g.name, cd.cc["name"]["pl" if cd.cc["defaultLang"] == "pl" else "cs"], "district", None, g.lat, g.lon)
        for g in cd.neighborhoods.values():
            parent = cd.districts.get(g.parent).name if g.parent in cd.districts else None
            self._add(g.name, parent, "place", None, g.lat, g.lon)
        for cat, p in cd.pois.items():
            for name, la, lo in zip(p["name"], p["lat"], p["lon"]):
                if name and "(dev)" not in str(name):
                    self._add(str(name), None, "poi", cat, float(la), float(lo))
        addr = cd.data_dir / "addresses.parquet"
        if addr.exists():
            t = pq.read_table(addr, columns=["street", "housenumber", "lat", "lon"])
            for st, hn, la, lo in zip(*(t.column(c).to_pylist() for c in ("street", "housenumber", "lat", "lon"))):
                if st:
                    self._add(f"{st} {hn}" if hn else str(st), None, "address", None, float(la), float(lo))
        log.info("%s: geocode index with %d entries", cd.city, len(self.entries))

    def _add(self, label, sublabel, kind, category, lat, lon):
        f = fold(label)
        if not f:
            return
        e = Entry(label, sublabel, kind, category, lat, lon, f, tuple(f.split()))
        i = len(self.entries)
        self.entries.append(e)
        for t in set(e.tokens):
            self.prefix.setdefault(t[:2], []).append(i)

    def search(self, q: str, limit: int = 8) -> list[dict]:
        fq = fold(q)
        qt = fq.split()
        if not qt:
            return []
        key = max(qt, key=len)[:2]
        scored = []
        for i in self.prefix.get(key, []):
            e = self.entries[i]
            if not all(any(et.startswith(t) for et in e.tokens) for t in qt):
                continue
            s = KIND_BOOST[e.kind]
            if e.folded == fq:
                s += 100
            elif e.folded.startswith(fq):
                s += 60
            s -= len(e.folded) * 0.1
            scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        out, seen = [], set()
        for _, i in scored:
            e = self.entries[i]
            dedup = (e.folded, e.kind, round(e.lat, 3), round(e.lon, 3))
            if dedup in seen:
                continue
            seen.add(dedup)
            out.append({"label": e.label, "sublabel": e.sublabel, "kind": e.kind, "category": e.category,
                        "lat": round(e.lat, 6), "lon": round(e.lon, 6), "h3": h3.latlng_to_cell(e.lat, e.lon, 9),
                        "source": "local"})
            if len(out) >= limit:
                break
        return out


def photon(cd: CityData, q: str, limit: int) -> list[dict]:
    if settings().offline:
        return []
    key = (cd.city, fold(q), limit)
    if key in _photon_cache:
        return _photon_cache[key]
    bbox = cd.cc["bbox"]
    try:
        r = httpx.get("https://photon.komoot.io/api/", params={"q": q, "limit": limit, "bbox": ",".join(map(str, bbox))},
                      headers=UA, timeout=3.0)
        r.raise_for_status()
        feats = r.json().get("features", [])
    except Exception as e:  # noqa: BLE001
        log.warning("photon failed: %s", e)
        return []
    out = []
    for f in feats:
        p = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"]
        if not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
            continue
        street = p.get("street")
        name = p.get("name") or (f"{street} {p.get('housenumber', '')}".strip() if street else None)
        if not name:
            continue
        sub = ", ".join(x for x in (p.get("district") or p.get("locality"), p.get("city")) if x) or None
        kind = "address" if p.get("housenumber") or p.get("type") in ("house", "street") else "place"
        out.append({"label": name, "sublabel": sub, "kind": kind, "category": None, "lat": round(lat, 6),
                    "lon": round(lon, 6), "h3": h3.latlng_to_cell(lat, lon, 9), "source": "photon"})
    _photon_cache[key] = out
    return out


def geocode(index: GeoIndex, q: str, limit: int) -> dict:
    items = index.search(q, limit)
    if len(items) < min(3, limit):
        seen = {(i["label"], round(i["lat"], 3)) for i in items}
        for it in photon(index.cd, q, limit):
            if (it["label"], round(it["lat"], 3)) not in seen:
                items.append(it)
            if len(items) >= limit:
                break
    return {"query": q, "items": items}

