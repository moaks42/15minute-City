"""Every endpoint's response validates against contracts/openapi.yaml (B DoD: OpenAPI matches the contract)."""
import pytest
import yaml
from validate_fixtures import check

from app.config import REPO_DIR
from app.models import encode_state
from conftest import persona_request

CITIES = ["krakow", "praha"]
ANCHOR = {"krakow": (50.0487, 19.9625), "praha": (50.0925, 14.4520)}


def ok(name, resp, schema):
    assert resp.status_code == 200, resp.text
    errors = check(name, resp.json(), schema)
    assert not errors, "\n".join(errors[:10])


def test_served_openapi_is_the_contract(client):
    contract = yaml.safe_load((REPO_DIR / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    assert client.get("/openapi.json").json() == contract


def test_health_and_cities(client):
    ok("health", client.get("/api/health"), "Health")
    ok("cities", client.get("/api/cities"), {"type": "array", "items": {"$ref": "#/components/schemas/City"}})


@pytest.mark.parametrize("city", CITIES)
def test_meta(client, city):
    ok("meta", client.get(f"/api/{city}/meta?lang=en"), "Meta")


@pytest.mark.parametrize("city", CITIES)
@pytest.mark.parametrize("aggregate", ["hex", "district", "neighborhood"])
def test_score(client, state, city, aggregate):
    la, lo = ANCHOR[city]
    req = persona_request(state, "parent", aggregate=aggregate, limit=10,
                          anchors=[{"id": "a1", "label": "Work", "lat": la, "lon": lo, "mode": "transit", "level": 5, "maxMinutes": 45}],
                          filters={"mustHave": [{"category": "pharmacy", "maxWalkMin": 15}], "maxNoiseDb": 70},
                          budget={"total": 900000, "monthlyRent": 25000})
    ok("score", client.post(f"/api/{city}/score", json=req), "ScoreResponse")


@pytest.mark.parametrize("city", CITIES)
@pytest.mark.parametrize("rank_by", ["green", "anchor:a1", "nonsense"])
def test_score_rank_by(client, state, city, rank_by):
    la, lo = ANCHOR[city]
    did = next(iter(state.cities[city].districts))
    for extra in ({"aggregate": "district"}, {"aggregate": "hex", "district": did, "includeCells": False}):
        req = persona_request(state, "parent", limit=5, rankBy=rank_by,
                              anchors=[{"id": "a1", "label": "Work", "lat": la, "lon": lo, "mode": "transit"}], **extra)
        ok("score", client.post(f"/api/{city}/score", json=req), "ScoreResponse")


@pytest.mark.parametrize("city", CITIES)
def test_score_nomatch(client, state, city):
    req = persona_request(state, "student", filters={"maxPricePerM2": 1, "maxRentPerM2": 1})
    r = client.post(f"/api/{city}/score", json=req)
    ok("score", r, "ScoreResponse")
    assert r.json()["count"]["passing"] == 0
    assert r.json()["relaxHint"]["filter"] == "price"


@pytest.mark.parametrize("city", CITIES)
def test_place_similar_commute(client, state, city):
    cd = state.cities[city]
    h = cd.cells[int(cd.habitable.nonzero()[0][0])]
    la, lo = ANCHOR[city]
    st = encode_state(persona_request(state, "senior", anchors=[{"id": "a1", "lat": la, "lon": lo, "mode": "bike"}]))
    ok("place", client.get(f"/api/{city}/place/{h}?lang=en&state={st}"), "Place")
    ok("place-nostate", client.get(f"/api/{city}/place/{h}"), "Place")
    ok("similar", client.get(f"/api/{city}/similar/{h}?limit=5"), "SimilarResponse")
    ok("commute", client.get(f"/api/{city}/commute?lat={la}&lon={lo}&mode=transit"), "CommuteResponse")
    ok("districts", client.get(f"/api/{city}/districts"), "DistrictList")
    ok("neighborhoods", client.get(f"/api/{city}/districts?level=neighborhood"), "DistrictList")
    ok("geocode", client.get(f"/api/{city}/geocode?q=ma"), "GeocodeResponse")
    ok("air", client.get(f"/api/{city}/live/air?lat={la}&lon={lo}"), "LiveAir")
    ok("departures", client.get(f"/api/{city}/live/departures?stopId=x"), "LiveDepartures")
    ok("pairs", client.get(f"/api/{city}/prefs/pairs?n=6"), "PrefPairs")


def test_twins(client, state):
    k = state.cities["krakow"]
    h = k.cells[int(k.habitable.nonzero()[0][10])]
    ok("twins", client.get(f"/api/twins?from=krakow&to=praha&h3={h}&limit=5&lang=pl"), "TwinsResponse")
    did = next(iter(k.districts))
    ok("twins-district", client.get(f"/api/twins?from=krakow&to=praha&district={did}"), "TwinsResponse")
    p = state.cities["praha"]
    ok("twins-rev", client.get(f"/api/twins?from=praha&to=krakow&h3={p.cells[int(p.habitable.nonzero()[0][0])]}"), "TwinsResponse")


def test_prefs_fit(client):
    choices = [{"a": {"green": 90, "price": 20}, "b": {"green": 20, "price": 80}, "choice": "a"},
               {"a": {"transit": 90, "green": 30}, "b": {"transit": 20, "green": 85}, "choice": "b"}]
    ok("fit", client.post("/api/prefs/fit", json={"choices": choices}), "PrefFitResponse")


def test_errors_use_error_schema(client):
    ok_codes = {"/api/nowhere/meta": 404, "/api/krakow/place/891e2040d4bffff": 404, "/api/twins?from=krakow&to=krakow&h3=x": 422}
    for url, code in ok_codes.items():
        r = client.get(url)
        assert r.status_code == code, (url, r.text)
        assert not check(url, r.json(), "Error")
    r = client.post("/api/krakow/score", json={"weights": {"green": 9}, "limit": 0})
    assert r.status_code == 422 and not check("422", r.json(), "Error")


def test_grid(client, state):
    r = client.get("/api/praha/grid")
    assert r.status_code == 200
    g = r.json()
    assert len(g["features"]) == state.cities["praha"].n
    assert g["features"][5]["id"] == 5
