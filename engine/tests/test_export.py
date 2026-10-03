"""Static fallback export: valid against StaticCriteriaScores and consistent with /score."""
import json

import numpy as np
from validate_fixtures import check

from app.export import export_all
from app.models import ScoreRequest
from app.scoring import compute


def test_static_export(tmp_path, state):
    paths = export_all(tmp_path, state.cities, state.cfg)
    assert {p.name for p in paths} == {"criteria_scores_krakow.json", "criteria_scores_praha.json"}
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        assert not check(p.name, data, "StaticCriteriaScores")
        cd = state.cities[data["city"]]
        assert len(data["cells"]) == cd.n and set(data["byPersona"]) == {"student", "working", "parent", "expecting", "senior"}
        # the web fallback formula reproduces the engine's match % (no anchors) within rounding
        w = state.cfg.persona("custom")["weights"]
        ctx = compute(cd, state.cfg, ScoreRequest(persona="custom", weights=w))
        lw = {int(k): v for k, v in data["levels"].items()}
        ws = np.array([lw[w[c]] for c in data["criteria"]], float)
        S = np.array([row[2:] for row in data["cells"]], float)
        M = np.rint(S @ ws / ws.sum())
        assert np.max(np.abs(M - ctx.M)) <= 1
