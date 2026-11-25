"""Find real repair businesses near the customer. Nothing here is generated: every name, phone number and
address comes from a listings source, and every trade also gets plain search links as a fallback.

Sources, best first:
- Google Places (New) Text Search, when GOOGLE_PLACES_API_KEY is set: phone, rating, reviews, website, open now.
- OpenStreetMap (Overpass API), free and keyless: name, phone, website, address. Coverage varies by city.
Geocoding a typed place ("USC, Los Angeles", "90007") uses OpenStreetMap Nominatim, which is free.
"""
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import httpx

from . import config, rules

NOMINATIM = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OVERPASS = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
GOOGLE_TEXT_SEARCH = "https://places.googleapis.com/v1/places:searchText"
# Nominatim's policy asks every app to identify itself; set CONTACT_USER_AGENT to your app name + contact URL/email.
USER_AGENT = os.environ.get("CONTACT_USER_AGENT", "home-repair-check/1.0 (self-hosted open-source app)")
RADIUS_M = 15000
MAX_PER_TRADE = 5
CACHE_TTL_S = 6 * 3600
GOOGLE_FIELDS = ",".join(f"places.{f}" for f in (
    "displayName", "formattedAddress", "nationalPhoneNumber", "internationalPhoneNumber", "rating",
    "userRatingCount", "websiteUri", "googleMapsUri", "location", "businessStatus", "currentOpeningHours.openNow"))


class LookupFailed(RuntimeError):
    """A listings source failed; the caller still returns the search links."""


def google_key() -> str | None:
    return os.environ.get("GOOGLE_PLACES_API_KEY") or None


def source() -> str:
    return "google" if google_key() else "openstreetmap"


# ------------------------------------------------------------------ small TTL cache + Nominatim throttle
_cache: dict = {}
_cache_lock = threading.Lock()


def _cached(key, fn):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_S:
            return hit[1]
    value = fn()
    with _cache_lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[key] = (now, value)
    return value


_nominatim_lock = threading.Lock()
_nominatim_last = [0.0]


def _nominatim(path: str, params: dict) -> list | dict:
    with _nominatim_lock:  # Nominatim allows at most 1 request per second
        wait = 1.05 - (time.time() - _nominatim_last[0])
        if wait > 0:
            time.sleep(wait)
        _nominatim_last[0] = time.time()
        return _get_json(f"{NOMINATIM}/{path}", params)


def _get_json(url, params):
    r = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=8)
    r.raise_for_status()
    return r.json()


def _post_overpass(query: str) -> dict:
    r = httpx.post(OVERPASS, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=7)
    r.raise_for_status()
    d = r.json()
    if "runtime error" in (d.get("remark") or ""):  # Overpass reports overload/timeouts inside a 200 response
        raise ValueError(d["remark"][:120])
    return d


def _post_google(body: dict) -> dict:
    r = httpx.post(GOOGLE_TEXT_SEARCH, json=body, timeout=10, headers={
        "X-Goog-Api-Key": google_key(), "X-Goog-FieldMask": GOOGLE_FIELDS})
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------ geocoding
def geocode(place: str) -> dict | None:
    place = " ".join(place.split())[:120]
    if not place:
        return None

    def run():
        hits = _nominatim("search", {"q": place, "format": "jsonv2", "limit": 1, "countrycodes": "us", "addressdetails": 1})
        if not hits:
            return None
        h = hits[0]
        return {"lat": float(h["lat"]), "lon": float(h["lon"]), "label": _short_label(h, place)}
    return _cached(("geo", place.lower()), run)


def reverse(lat: float, lon: float) -> dict:
    def run():
        try:
            h = _nominatim("reverse", {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 14, "addressdetails": 1})
            return {"lat": lat, "lon": lon, "label": _short_label(h, "your location")}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"lat": lat, "lon": lon, "label": "your location"}
    return _cached(("rev", round(lat, 3), round(lon, 3)), run)


def _short_label(hit: dict, fallback: str) -> str:
    a = hit.get("address") or {}
    area = a.get("neighbourhood") or a.get("suburb") or a.get("city_district")
    city = a.get("city") or a.get("town") or a.get("village") or a.get("county")
    state = a.get("state")
    parts = [x for x in (hit.get("name") if hit.get("name") and hit.get("category") not in ("place", "boundary") else None,
                         area, city, state) if x]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return ", ".join(out[:3]) or fallback


# ------------------------------------------------------------------ helpers
def distance_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def search_links(query: str, where_label: str) -> dict:
    q = f"{query} near {where_label}"
    return {"google_maps": "https://www.google.com/maps/search/?api=1&query=" + quote_plus(q),
            "yelp": f"https://www.yelp.com/search?find_desc={quote_plus(query)}&find_loc={quote_plus(where_label)}"}


def _directions(lat, lon):
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"


# ------------------------------------------------------------------ OpenStreetMap
def _osm_address(t: dict) -> str | None:
    street = " ".join(x for x in (t.get("addr:housenumber"), t.get("addr:street")) if x)
    city = t.get("addr:city")
    line = ", ".join(x for x in (street, city, t.get("addr:state"), t.get("addr:postcode")) if x)
    return line or None


def _osm_row(name, t, lat, lon, elat, elon):
    return {"name": name, "phone": t.get("phone") or t.get("contact:phone"),
            "website": t.get("website") or t.get("contact:website"), "email": t.get("email") or t.get("contact:email"),
            "address": _osm_address(t), "hours": t.get("opening_hours"),
            "distance_km": round(distance_km(lat, lon, elat, elon), 1),
            "directions": _directions(elat, elon), "rating": None, "reviews": None, "open_now": None}


def _overpass_rows(crafts_by_trade, lat, lon):
    crafts = sorted({c for cs in crafts_by_trade.values() for c in cs})
    pattern = "|".join(crafts)
    q = f'[out:json][timeout:6];nwr["craft"~"^({pattern})$"](around:{RADIUS_M},{lat:.5f},{lon:.5f});out center tags 200;'
    elements = _cached(("osm", pattern, round(lat, 2), round(lon, 2)), lambda: _post_overpass(q).get("elements", []))
    out = {}
    for trade, cs in crafts_by_trade.items():
        rows = []
        for e in elements:
            t = e.get("tags", {})
            elat = e.get("lat") or e.get("center", {}).get("lat")
            elon = e.get("lon") or e.get("center", {}).get("lon")
            if t.get("name") and t.get("craft") in cs and elat is not None:
                rows.append(_osm_row(t["name"], t, lat, lon, elat, elon))
        out[trade] = rows
    return out


def _nominatim_rows(crafts_by_trade, lat, lon):
    """Backup when the Overpass servers are busy: Nominatim's business search inside a ~15 km box."""
    d = RADIUS_M / 111_000
    box = f"{lon - d / math.cos(math.radians(lat)):.4f},{lat + d:.4f},{lon + d / math.cos(math.radians(lat)):.4f},{lat - d:.4f}"
    out = {}
    for trade, cs in crafts_by_trade.items():
        rows = []
        for craft in cs[:2]:
            hits = _cached(("nomi", craft, round(lat, 2), round(lon, 2)), lambda c=craft: _nominatim("search", {
                "q": c, "format": "jsonv2", "limit": 15, "bounded": 1, "viewbox": box, "extratags": 1, "addressdetails": 1}))
            for h in hits:
                if h.get("type") != craft or not h.get("name"):
                    continue
                a = h.get("address") or {}
                t = dict(h.get("extratags") or {})
                t.setdefault("addr:housenumber", a.get("house_number"))
                t.setdefault("addr:street", a.get("road"))
                t.setdefault("addr:city", a.get("city") or a.get("town"))
                t.setdefault("addr:state", a.get("state"))
                t.setdefault("addr:postcode", a.get("postcode"))
                rows.append(_osm_row(h["name"], {k: v for k, v in t.items() if v}, lat, lon, float(h["lat"]), float(h["lon"])))
        out[trade] = rows
    return out


_overpass_down_until = [0.0]
OVERPASS_COOLDOWN_S = 300  # after a failure, go straight to Nominatim for a while instead of waiting on a busy server


def osm_search(crafts_by_trade: dict[str, list[str]], lat: float, lon: float) -> tuple[dict[str, list[dict]], str]:
    """OpenStreetMap listings per trade. Overpass first (complete within the radius); Nominatim if it's busy."""
    crafts_by_trade = {t: cs for t, cs in crafts_by_trade.items()}
    if not any(crafts_by_trade.values()):
        return {t: [] for t in crafts_by_trade}, "overpass"
    try:
        if time.time() < _overpass_down_until[0]:
            raise ValueError("Overpass recently failed; skipping it for now")
        rows, via = _overpass_rows(crafts_by_trade, lat, lon), "overpass"
    except (httpx.HTTPError, ValueError) as e:
        if not str(e).startswith("Overpass recently failed"):
            _overpass_down_until[0] = time.time() + OVERPASS_COOLDOWN_S
        try:
            rows, via = _nominatim_rows(crafts_by_trade, lat, lon), "nominatim"
        except (httpx.HTTPError, ValueError) as e:
            raise LookupFailed(f"OpenStreetMap lookup failed: {type(e).__name__}") from e
    out = {}
    for trade, rs in rows.items():
        uniq = {(r["name"], r["phone"]): r for r in rs}.values()  # the same business can be mapped twice
        out[trade] = sorted(uniq, key=lambda r: (r["phone"] is None, r["distance_km"]))[:MAX_PER_TRADE]
    return out, via


# ------------------------------------------------------------------ Google Places
def google_search(query: str, lat: float | None, lon: float | None, where_label: str) -> list[dict]:
    body = {"textQuery": query if lat is not None else f"{query} near {where_label}", "maxResultCount": MAX_PER_TRADE + 2}
    if lat is not None:
        body["locationBias"] = {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": float(RADIUS_M)}}

    def run():
        return _post_google(body).get("places", [])
    try:
        places = _cached(("g", query, where_label.lower(), round(lat or 0, 2), round(lon or 0, 2)), run)
    except (httpx.HTTPError, ValueError) as e:
        raise LookupFailed(f"Google Places lookup failed: {type(e).__name__}") from e
    rows = []
    for p in places:
        if p.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
            continue
        loc = p.get("location") or {}
        d = (round(distance_km(lat, lon, loc["latitude"], loc["longitude"]), 1)
             if lat is not None and "latitude" in loc else None)
        rows.append({"name": (p.get("displayName") or {}).get("text", "Unnamed"),
                     "phone": p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber"),
                     "website": p.get("websiteUri"), "email": None, "address": p.get("formattedAddress"), "hours": None,
                     "distance_km": d, "directions": p.get("googleMapsUri"),
                     "rating": p.get("rating"), "reviews": p.get("userRatingCount"),
                     "open_now": (p.get("currentOpeningHours") or {}).get("openNow")})
    return rows[:MAX_PER_TRADE]


# ------------------------------------------------------------------ main entry
def find(issue_id: str, place: str | None = None, lat: float | None = None, lon: float | None = None) -> dict:
    issue = rules.issues()[issue_id]
    trades = issue["pros"]
    if lat is not None and lon is not None:
        where = reverse(lat, lon)
    elif place and place.strip():
        try:
            where = geocode(place)
        except (httpx.HTTPError, ValueError) as e:
            where = None
            if not google_key():
                raise LookupFailed(f"Couldn't look up that place: {type(e).__name__}") from e
        if where is None:
            if not google_key():
                return {"found": False, "message": f'Couldn\'t find "{place.strip()[:80]}". Try a city, neighborhood or ZIP code.'}
            where = {"lat": None, "lon": None, "label": place.strip()[:80]}
    else:
        return {"found": False, "message": "Add a city, neighborhood or ZIP code to see repair pros near you."}

    src, errors = source(), []
    results: dict[str, list] = {t["label"]: [] for t in trades}
    try:
        if src == "google":
            with ThreadPoolExecutor(max_workers=len(trades)) as ex:
                futs = {t["label"]: ex.submit(google_search, t["query"], where["lat"], where["lon"], where["label"]) for t in trades}
                for label, f in futs.items():
                    try:
                        results[label] = f.result()
                    except LookupFailed as e:
                        errors.append(str(e))
        else:
            results, _via = osm_search({t["label"]: t["osm"] for t in trades}, where["lat"], where["lon"])
    except LookupFailed as e:
        errors.append(str(e))

    return {
        "found": True, "source": src, "where": where, "radius_km": RADIUS_M // 1000,
        "trades": [{"label": t["label"], "query": t["query"], "results": results.get(t["label"], []),
                    "links": search_links(t["query"], where["label"])} for t in trades],
        "errors": errors,
        "attribution": "Listings from Google Places" if src == "google" else "Listings © OpenStreetMap contributors",
        "note": ("Listings come straight from the source and aren't vetted. Check licensing, insurance and reviews "
                 "before you hire, and get more than one quote."),
    }
