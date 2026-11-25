"""Contact lookup, with every network call replaced: no request leaves the machine during tests."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from repaircheck import pros, rules

USC = {"lat": 34.0219, "lon": -118.2859, "label": "University Park, Los Angeles, California"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    pros._cache.clear()
    pros._overpass_down_until[0] = 0.0
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.setattr(pros, "geocode", lambda place: dict(USC) if "nowhere" not in place else None)
    monkeypatch.setattr(pros, "reverse", lambda lat, lon: {"lat": lat, "lon": lon, "label": "your location"})

    def no_network(*a, **k):
        raise AssertionError("tests must not hit the network")
    for fn in ("_post_overpass", "_post_google", "_nominatim"):
        monkeypatch.setattr(pros, fn, no_network)


def node(name, craft, lat, lon, **tags):
    return {"type": "node", "lat": lat, "lon": lon, "tags": {"name": name, "craft": craft, **tags}}


def test_every_problem_names_the_trades_to_call():
    for issue in rules.knowledge()["issues"]:
        assert issue["pros"], issue["id"]
        for t in issue["pros"]:
            assert t["label"] and t["query"] and isinstance(t["osm"], list)


def test_openstreetmap_listings_callable_first_then_nearest(monkeypatch):
    monkeypatch.setattr(pros, "_post_overpass", lambda q: {"elements": [
        node("Far Plumbing", "plumber", 34.10, -118.29, phone="+1 323 555 0100"),
        node("Near Plumbing", "plumber", 34.025, -118.285, phone="+1 213 555 0101", **{"addr:street": "Figueroa St"}),
        node("No Phone Plumbing", "plumber", 34.022, -118.286),
        node("Some Electrician", "electrician", 34.02, -118.28, phone="+1 213 555 0102"),
        {"type": "node", "lat": 34.02, "lon": -118.28, "tags": {"craft": "plumber"}},  # unnamed: skipped
    ]})
    r = pros.find("plumbing_leak", "USC, Los Angeles")
    names = [x["name"] for x in r["trades"][0]["results"]]
    assert r["source"] == "openstreetmap" and names == ["Near Plumbing", "Far Plumbing", "No Phone Plumbing"]
    first = r["trades"][0]["results"][0]
    assert first["phone"] == "+1 213 555 0101" and first["address"] == "Figueroa St" and first["distance_km"] < 1
    assert "google.com/maps" in r["trades"][0]["links"]["google_maps"] and "yelp.com" in r["trades"][0]["links"]["yelp"]
    assert "OpenStreetMap" in r["attribution"]


def test_busy_overpass_falls_back_to_nominatim(monkeypatch):
    def busy(q):
        raise httpx.HTTPStatusError("502", request=httpx.Request("POST", "x"), response=httpx.Response(502))
    monkeypatch.setattr(pros, "_post_overpass", busy)
    monkeypatch.setattr(pros, "_nominatim", lambda path, params: [
        {"name": "A & M Electric", "type": "electrician", "lat": "34.07", "lon": "-118.34",
         "extratags": {"phone": "+1 323-935-1144"}, "address": {"road": "Beverly Boulevard", "city": "Los Angeles"}},
        {"name": "Electric Avenue", "type": "street", "lat": "34.0", "lon": "-118.3"}])  # not a business: skipped
    r = pros.find("outlet_damage", "USC")
    res = r["trades"][0]["results"]
    assert [x["name"] for x in res] == ["A & M Electric"] and res[0]["address"] == "Beverly Boulevard, Los Angeles"


def test_every_source_down_still_gives_search_links(monkeypatch):
    def down(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(pros, "_post_overpass", down)
    monkeypatch.setattr(pros, "_nominatim", down)
    r = pros.find("water_stain", "USC")
    assert r["found"] and r["errors"] and all(t["results"] == [] and t["links"]["google_maps"] for t in r["trades"])


def test_google_places_when_a_key_is_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    seen = []

    def google(body):
        seen.append(body)
        return {"places": [
            {"displayName": {"text": "Trojan Plumbing"}, "nationalPhoneNumber": "(213) 555-0199", "rating": 4.8,
             "userRatingCount": 312, "formattedAddress": "123 Figueroa St, Los Angeles, CA", "websiteUri": "https://example.com",
             "googleMapsUri": "https://maps.google.com/?cid=1", "location": {"latitude": 34.03, "longitude": -118.28},
             "businessStatus": "OPERATIONAL", "currentOpeningHours": {"openNow": True}},
            {"displayName": {"text": "Closed Co"}, "businessStatus": "CLOSED_PERMANENTLY"}]}
    monkeypatch.setattr(pros, "_post_google", google)
    r = pros.find("plumbing_leak", "USC")
    x = r["trades"][0]["results"]
    assert r["source"] == "google" and len(x) == 1 and x[0]["rating"] == 4.8 and x[0]["open_now"] is True
    assert seen[0]["textQuery"] == "plumber" and seen[0]["locationBias"]["circle"]["center"]["latitude"] == USC["lat"]


def test_no_location_or_unknown_place_asks_for_one():
    assert not pros.find("mold")["found"]
    r = pros.find("mold", "nowhere-ville-zzz")
    assert not r["found"] and "Couldn't find" in r["message"]


def test_browser_location_skips_geocoding(monkeypatch):
    monkeypatch.setattr(pros, "_post_overpass", lambda q: {"elements": []})
    r = pros.find("roof_damage", lat=34.02, lon=-118.28)
    assert r["where"]["lat"] == 34.02 and r["trades"][0]["label"] == "Roofer"


def test_pros_api(monkeypatch):
    monkeypatch.setattr(pros, "_post_overpass", lambda q: {"elements": [node("Near Plumbing", "plumber", 34.025, -118.285)]})
    main._rate.clear()
    with TestClient(main.app) as c:
        r = c.post("/api/pros", json={"issue_id": "plumbing_leak", "place": "USC, Los Angeles"}).json()
        assert r["trades"][0]["results"][0]["name"] == "Near Plumbing"
        assert c.post("/api/pros", json={"issue_id": "nope", "place": "LA"}).status_code == 404
        assert c.post("/api/pros", json={"issue_id": "mold", "lat": 200, "lon": 0}).status_code == 422
        assert c.get("/api/meta").json()["contacts_source"] == "openstreetmap"


def test_distance():
    assert abs(pros.distance_km(34.0219, -118.2859, 34.0522, -118.2437) - 5.1) < 0.3  # USC to downtown LA


def test_busy_overpass_is_skipped_for_a_while(monkeypatch):
    calls = []

    def busy(q):
        calls.append(q)
        raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(pros, "_post_overpass", busy)
    monkeypatch.setattr(pros, "_nominatim", lambda path, params: [])
    pros.find("outlet_damage", "USC")
    pros._cache.clear()
    pros.find("plumbing_leak", "USC")
    assert len(calls) == 1  # the second lookup didn't wait on the busy server again
