"""Partial real data (what A delivers first) must still serve: no travel times, no POIs, all-NaN columns."""
import shutil

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from app.data import load_city
from app.models import ScoreRequest
from app.scoring import compute, place_detail, score_response


def test_partial_data(tmp_path, state):
    src = state.cities["krakow"].data_dir
    dst = tmp_path / "krakow"
    shutil.copytree(src, dst)
    for f in ("travel_times.npz", "pois.parquet", "addresses.parquet", "neighborhoods.geojson"):
        (dst / f).unlink(missing_ok=True)
    t = pq.read_table(dst / "features.parquet")
    for col in ("environment.noise_db", "price.buy_per_m2", "education.nursery_walk_min"):
        i = t.column_names.index(col)
        t = t.set_column(i, col, pa.array(np.full(t.num_rows, np.nan, dtype=np.float32)))
    pq.write_table(t, dst / "features.parquet")

    cd = load_city("krakow", state.cfg, tmp_path, "real")
    assert cd.modes() == [] and cd.pois == {}
    assert cd.coverage[cd.spec_index("environment.noise_db")] == 0

    p = state.cfg.persona("working")
    req = ScoreRequest(persona="working", weights=p["weights"], lang="pl",
                       anchors=[{"id": "a1", "lat": 50.0487, "lon": 19.9625}],
                       filters={"maxPricePerM2": 15000, "maxNoiseDb": 60}, budget={"total": 800000})
    ctx = compute(cd, state.cfg, req)
    assert "commute" in ctx.excluded                       # no travel times → commute excluded, not a crash
    assert ctx.passing.sum() == cd.habitable.sum()         # all-NaN price/noise → filters are skipped
    out = score_response(cd, state.cfg, req)
    assert out["top"] and out["top"][0]["price"] is None and out["top"][0]["budgetM2"] is None
    assert out["top"][0]["anchors"][0]["minutes"] is None
    detail = place_detail(cd, state.cfg, req, cd.index[out["top"][0]["id"]])
    assert detail["nearest"] == []
    assert all(i["column"] != "environment.noise_db" for i in detail["indicators"])
