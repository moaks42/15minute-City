"""Scoring behaviour (README §11 B DoD)."""
import math
import time

import numpy as np
import pytest

from app.explain import display_value
from app.models import ScoreRequest
from app.scoring import compute, score_response
from conftest import persona_request

CITIES = ["krakow", "praha"]


def req(state, persona="custom", **kw) -> ScoreRequest:
    return ScoreRequest.model_validate(persona_request(state, persona, **kw))


def test_both_cities_load(client, state):
    h = client.get("/api/health").json()
    assert set(h["dataVersion"]) == {"krakow", "praha"}
    for city in CITIES:
        cd = state.cities[city]
        assert cd.n > 1000 and cd.habitable.sum() > 500
        assert (cd.coverage > 0).sum() >= 10


@pytest.mark.parametrize("city", CITIES)
def test_monotonicity(state, city):
    """Raising a criterion's level never lowers the relative rank of the cell that is best in that criterion."""
    cd, cfg = state.cities[city], state.cfg
    base = req(state, "custom")
    ctx0 = compute(cd, cfg, base)
    hab = np.flatnonzero(cd.habitable)
    for c in ctx0.crit:
        best = hab[np.argmax(ctx0.crit[c][hab])]
        prev = None
        for level in range(0, 6):
            r = base.model_copy(update={"weights": {**base.weights, c: level}})
            ctx = compute(cd, cfg, r)
            rank = int(np.sum(ctx.Mf[hab] > ctx.Mf[best] + 1e-9))
            if prev is not None:
                assert rank <= prev, f"{city}/{c}: rank of best cell went {prev} → {rank} at level {level}"
            prev = rank


@pytest.mark.parametrize("city", CITIES)
def test_filters_exclude(state, city):
    cd, cfg = state.cities[city], state.cfg
    hab = cd.habitable
    price = cd.col_filled(cd.cc["price"]["column"])
    noise = cd.col_filled("environment.noise_db")
    smkt = cd.col("shops.supermarket_walk_min")
    pmax = float(np.nanpercentile(price[hab], 70))
    nmax = float(np.nanpercentile(noise[hab], 80))
    wmax = max(1.0, float(np.nanpercentile(smkt[hab], 80)))
    field = cd.cc["price"]["filterField"]
    r = req(state, "working", filters={field: pmax, "maxNoiseDb": nmax,
                                       "mustHave": [{"category": "supermarket", "maxWalkMin": wmax}]})
    ctx = compute(cd, cfg, r)
    p = ctx.passing
    assert 0 < p.sum() < hab.sum()
    assert np.all(hab[p])
    assert np.all(~(price[p] > pmax))
    assert np.all(~(noise[p] > nmax))
    assert np.all(smkt[p] <= wmax)
    out = score_response(cd, cfg, r)
    assert all(t["passes"] for t in out["top"])
    assert out["count"]["passing"] == int(p.sum())
    assert sum(c[2] for c in out["cells"]) == int(p.sum())


@pytest.mark.parametrize("city", CITIES)
def test_commute_filter(state, city):
    cd, cfg = state.cities[city], state.cfg
    la, lo = cd.cc["center"]
    r = req(state, "working", anchors=[{"id": "a1", "lat": la, "lon": lo, "mode": "transit", "maxMinutes": 20}])
    ctx = compute(cd, cfg, r)
    assert ctx.passing.sum() > 0
    assert np.all(ctx.anchor_min["a1"][ctx.passing] <= 20)


@pytest.mark.parametrize("city", CITIES)
def test_relax_hint(state, city):
    cd, cfg = state.cities[city], state.cfg
    field = cd.cc["price"]["filterField"]
    r = req(state, "parent", filters={field: 1, "mustHave": [{"category": "pharmacy", "maxWalkMin": 20}]}, lang="en")
    out = score_response(cd, cfg, r)
    assert out["count"]["passing"] == 0 and out["top"] == []
    hint = out["relaxHint"]
    assert hint["filter"] == "price"
    expected = compute(cd, cfg, req(state, "parent", filters={"mustHave": [{"category": "pharmacy", "maxWalkMin": 20}]})).passing.sum()
    assert hint["passingAfter"] == expected
    assert str(expected) in hint["text"].replace(",", "")


def test_outside_anchor_is_unreachable(state):
    cd, cfg = state.cities["krakow"], state.cfg
    r = req(state, "working", anchors=[{"id": "a1", "lat": 50.0925, "lon": 14.4520}])  # Karlín (Praha)
    ctx = compute(cd, cfg, r)
    assert ctx.anchor_min["a1"] is None
    assert "commute" in ctx.excluded


@pytest.mark.parametrize("city", CITIES)
def test_determinism(state, city):
    cd, cfg = state.cities[city], state.cfg
    r = req(state, "expecting", anchors=[{"id": "a", "lat": cd.cc["center"][0], "lon": cd.cc["center"][1]}], aggregate="hex")
    a, b = score_response(cd, cfg, r), score_response(cd, cfg, r)
    a.pop("computeMs"), b.pop("computeMs")
    assert a == b


@pytest.mark.parametrize("city", CITIES)
@pytest.mark.parametrize("lang", ["pl", "cs", "en"])
def test_explanations_match_raw(state, city, lang):
    cd, cfg = state.cities[city], state.cfg
    out = score_response(cd, cfg, req(state, "student", lang=lang, limit=20))
    n = 0
    names = [t["name"] for t in out["top"]]
    assert len(names) == len(set(names)), "top must list distinct neighbourhoods"
    for t in out["top"]:
        i = cd.index[t["id"]]
        for e in t["highlights"] + t["warnings"]:
            assert e["text"], e
            if e["indicator"] is None:
                continue
            raw = float(cd.col(e["indicator"])[i])
            assert not math.isnan(raw), f"explanation from an imputed value: {e}"
            assert math.isclose(e["value"], raw, rel_tol=1e-3, abs_tol=0.01), (e, raw)
            spec = next(s for s in cd.specs if s.column == e["indicator"])
            assert display_value(raw, spec.unit, lang, spec.decimals) in e["text"], (e, raw)
            n += 1
    assert n > 10


@pytest.mark.parametrize("city", CITIES)
def test_imputed_never_explained(state, city):
    cd, cfg = state.cities[city], state.cfg
    out = score_response(cd, cfg, req(state, "expecting", limit=50))
    for t in out["top"]:
        for e in t["highlights"] + t["warnings"]:
            if e["indicator"]:
                assert e["indicator"] not in t["imputed"]


def test_walk_factor_lowers_walk_scores(state):
    cd = state.cities["praha"]
    j = cd.spec_index("transit.stop_walk_min")
    s1, s135 = cd.normalized(1.0)[:, j], cd.normalized(1.35)[:, j]
    assert np.all(s135 <= s1 + 1e-6) and np.any(s135 < s1)


def test_crime_never_a_warning(state):
    for city in CITIES:
        out = score_response(state.cities[city], state.cfg, req(state, "senior", limit=100))
        assert all(w["indicator"] != "safety.crime_per_1000" for t in out["top"] for w in t["warnings"])


def test_p95_latency(state):
    """p95 < 150 ms server-side on the biggest city (README §6.2)."""
    cd, cfg = state.cities["praha"], state.cfg
    rng = np.random.default_rng(0)
    personas = ["student", "working", "parent", "expecting", "senior", "custom"]
    la, lo = cd.cc["center"]
    times = []
    for k in range(40):
        p = personas[k % len(personas)]
        w = {c: int(rng.integers(0, 6)) for c in cfg.criterion_ids}
        r = req(state, p, weights=w, anchors=[{"id": "a", "lat": la + 0.01, "lon": lo, "level": 5}],
                filters={"mustHave": [{"category": "pharmacy", "maxWalkMin": 10}]}, aggregate=["hex", "district"][k % 2])
        t = time.perf_counter()
        score_response(cd, cfg, r)
        times.append((time.perf_counter() - t) * 1000)
    p95 = float(np.percentile(times, 95))
    print(f"praha /score p95 = {p95:.1f} ms (n={cd.n})")
    assert p95 < 150


def test_geocode_accent_insensitive(client):
    r = client.get("/api/praha/geocode?q=zizkov").json()
    assert any(i["label"] == "Žižkov" for i in r["items"])
    r = client.get("/api/krakow/geocode?q=zablocie").json()
    assert any(i["label"] == "Zabłocie" for i in r["items"])
    r = client.get("/api/krakow/geocode?q=lobzow").json()
    assert any(i["label"] == "Łobzów" for i in r["items"])


def test_geocode_addresses(client, state):
    if not (state.cities["krakow"].data_dir / "addresses.parquet").exists():
        import pytest
        pytest.skip("no addresses.parquet for krakow")
    r = client.get("/api/krakow/geocode?q=rakowicka").json()
    assert r["items"] and all(i["label"].startswith("Rakowicka") for i in r["items"][:3])
    r = client.get("/api/krakow/geocode?q=rakowicka 3").json()
    assert r["items"][0]["label"] == "Rakowicka 3"
    r = client.get("/api/praha/geocode?q=vinohradska").json()
    assert r["items"][0]["label"].startswith("Vinohradská")


@pytest.mark.parametrize("city", CITIES)
def test_explanations_are_meaningful(state, city):
    """A highlight's indicator scores well, a warning's badly (no "⚠ lit streets 98%")."""
    cd, cfg = state.cities[city], state.cfg
    for persona in ("student", "parent", "senior"):
        out = score_response(cd, cfg, req(state, persona, limit=30))
        for t in out["top"]:
            i = cd.index[t["id"]]
            for e, good in [(e, True) for e in t["highlights"]] + [(e, False) for e in t["warnings"]]:
                if e["indicator"] is None:
                    continue
                j = next(j for j, s in enumerate(cd.specs) if s.column == e["indicator"])
                s = float(cd.normalized(state.cfg.persona(persona)["walkFactor"])[i, j])
                assert (s >= 60) if good else (s <= 40), (persona, e, s)


@pytest.mark.parametrize("city", CITIES)
def test_only_level_ratios_matter(state, city):
    """Match % is a weighted average: all 😐, all 🤩 and all skipped (equal-weight fallback) give the same map. The
    web tells the skipped cases apart via weightsUsed/excludedCriteria and shows a neutral state instead."""
    cd, cfg = state.cities[city], state.cfg
    ids = cfg.criterion_ids
    maps = [compute(cd, cfg, req(state, weights={c: lv for c in ids})).M for lv in (0, 1, 5)]
    assert np.array_equal(maps[0], maps[1]) and np.array_equal(maps[1], maps[2])
    for only in (None, "commute"):  # nothing rated; only the commute, but no places
        out = score_response(cd, cfg, req(state, weights={c: 5 if c == only else 0 for c in ids}, limit=1))
        assert not any(lv > 0 and c not in out["excludedCriteria"] for c, lv in out["weightsUsed"].items())


def test_krakow_crime_shows_decimals(state):
    """Kraków's source counts only public-space offences (0.2–5 per 1,000), so whole numbers would read "0"."""
    cd = state.cities["krakow"]
    s = cd.specs[cd.spec_index("safety.crime_per_1000")]
    assert s.decimals == 1 and "public-space" in s.label["en"].lower()
    low = float(np.nanmin(cd.col("safety.crime_per_1000")))
    assert display_value(low, s.unit, "pl", s.decimals) not in ("0", "0,0")


def test_noise_within_band_range(state):
    """A mean of 5-dB band values cannot leave the bands' range (FFT round-off at the edge of the Praha noise map
    once produced 0–175 dB)."""
    for city in CITIES:
        v = state.cities[city].col("environment.noise_db")
        v = v[~np.isnan(v)]
        assert 30 <= v.min() and v.max() <= 85, (city, v.min(), v.max())


def test_twin_similarity_is_calibrated(state):
    """distance_sim: identical → 1, two random places → ≈ 0 (cosine's (cos + 1) / 2 called them ≈ 50 % similar)."""
    from app import ml
    P = state.pooled
    k, p = state.cities["krakow"], state.cities["praha"]
    Zk, Zp, ref = P.Z["krakow"], P.Z["praha"], P.d_ref[("krakow", "praha")]
    i = int(np.flatnonzero(k.habitable)[10])
    assert ml.distance_sim(Zk[i], Zk[i], P.d_ref[("krakow", "krakow")])[0] == pytest.approx(1.0)
    rng = np.random.default_rng(1)
    a, b = rng.choice(np.flatnonzero(k.habitable), 2000), rng.choice(np.flatnonzero(p.habitable), 2000)
    assert abs(np.median(1 - np.linalg.norm(Zk[a] - Zp[b], axis=1) / ref)) < 0.05
    best = np.sort(ml.distance_sim(Zk[i], Zp[p.habitable], ref))[-5:]
    assert 0 < best.min() <= best.max() < 1
