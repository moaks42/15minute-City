import os
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1]
os.environ.setdefault("KOMPAS_OFFLINE", "1")                     # no live HTTP in tests
os.environ.setdefault("MODELS_DIR", str(ENGINE / ".devdata" / "models"))
sys.path.insert(0, str(ENGINE.parent / "contracts" / "tools"))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def state(client):
    from app.main import S
    return S


def persona_request(state, persona="custom", **kw):
    p = state.cfg.persona(persona)
    return {"v": 1, "persona": persona, "weights": dict(p["weights"]), **kw}
