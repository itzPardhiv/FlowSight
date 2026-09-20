import json
import math
import sys
from pathlib import Path

# Add backend directory to sys.path so app can be imported
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.geo_utils import (
    haversine_distance,
    distance_matrix,
    interpolate_route,
    points_within_radius,
    nearest_location,
    generate_circle_polygon,
)
from app.impact_engine import impact_engine, classify_exposure

client = TestClient(app)


def assert_no_nan_or_inf(obj, path="root"):
    """Recursively check that no NaN or Infinity exists in a JSON-like object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert_no_nan_or_inf(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            assert_no_nan_or_inf(item, f"{path}[{i}]")
    elif isinstance(obj, float):
        assert not math.isnan(obj), f"Found NaN at {path}"
        assert not math.isinf(obj), f"Found Infinity at {path}"


def test_1_haversine():
    print("Test 1: Haversine calculation...")
    # Zero distance
    d0 = haversine_distance(17.385, 78.4867, 17.385, 78.4867)
    assert d0 == 0.0, f"Expected 0.0, got {d0}"

    # Symmetry
    d1 = haversine_distance(17.385, 78.4867, 17.420, 78.4800)
    d2 = haversine_distance(17.420, 78.4800, 17.385, 78.4867)
    assert d1 == d2, f"Expected symmetry {d1} == {d2}"
    assert 3.5 < d1 < 4.5, f"Expected ~3.9 km, got {d1}"

    # Distance matrix
    coords1 = [(17.385, 78.4867), (17.365, 78.4600)]
    coords2 = [(17.420, 78.4800), (17.385, 78.4867)]
    mat = distance_matrix(coords1, coords2)
    assert mat.shape == (2, 2)
    assert mat[0, 1] == 0.0  # Same point
    print("  [PASS] Haversine and Distance Matrix verified.")


def test_2_radius_search():
    print("Test 2: Radius search...")
    df = impact_engine.get_df()
    assert len(df) == 1013, f"Expected 1013 locations, got {len(df)}"

    # Search around first location (3353: lat=17.365, lon=78.46)
    subset = points_within_radius(df, 17.365, 78.46, radius_km=2.0)
    assert not subset.empty, "Subset within 2km should not be empty"
    assert (subset["distance_km"] <= 2.0).all(), "All distances must be <= 2.0 km"

    # Check nearest location
    nearest, dist = nearest_location(df, 17.3651, 78.4601)
    assert nearest["location_id"] == 3353
    assert dist < 0.1
    print("  [PASS] Radius search and nearest location verified.")


def test_3_location_impact_endpoint():
    print("Test 3: Single location impact endpoint (/api/locations/{id}/impact)...")
    res = client.get("/api/locations/3353/impact")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert data["location"]["location_id"] == 3353
    assert "impact_radius" in data
    assert "recommended_radius_km" in data["impact_radius"]
    assert len(data["impact_radius"]["bands"]) >= 5
    assert "nearby_exposure" in data
    assert "route_exposure" in data
    assert "action" in data
    assert "disclaimer" in data
    print("  [PASS] Single location impact endpoint verified.")


def test_4_areas_endpoint():
    print("Test 4: Areas endpoint (/api/impact/areas/{location_id})...")
    res = client.get("/api/impact/areas/3353?radius_km=2.0&limit=50")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert data["origin_location_id"] == 3353
    assert data["radius_km"] == 2.0
    assert "locations" in data
    assert len(data["locations"]) > 0

    # Verify sorting: risk_score descending
    scores = [loc["risk_score"] for loc in data["locations"]]
    assert scores == sorted(scores, reverse=True), "Locations must be sorted by risk_score descending"
    print("  [PASS] Areas endpoint verified.")


def test_5_route_endpoint():
    print("Test 5: Route exposure endpoint (/api/impact/route)...")
    res = client.get(
        "/api/impact/route?start_lat=17.385&start_lon=78.4867&end_lat=17.42&end_lon=78.48&corridor_km=0.25&samples=30"
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert "route" in data
    assert "exposure" in data
    assert "segments" in data
    assert len(data["segments"]) == 30
    assert data["segments"][0]["sequence"] == 1
    assert "exposure_level" in data["exposure"]
    assert "disclaimer" in data
    print("  [PASS] Route exposure endpoint verified.")


def test_6_routes_ranking_endpoint():
    print("Test 6: Ranked routes endpoint (/api/impact/routes)...")
    res = client.get("/api/impact/routes?limit=5")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert "corridors" in data
    assert len(data["corridors"]) <= 5
    for c in data["corridors"]:
        assert "Risk Corridor" in c["name"]
        assert "start" in c
        assert "end" in c
        assert "average_risk_score" in c
        assert "exposure_level" in c
    print("  [PASS] Ranked routes endpoint verified.")


def test_7_summary_endpoint():
    print("Test 7: Summary endpoint (/api/impact/summary)...")
    res = client.get("/api/impact/summary")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert data["total_locations"] == 1013
    assert data["very_high_locations"] >= 0
    assert data["high_locations"] >= 0
    assert data["estimated_high_risk_area_km2"] > 0
    assert "highest_risk_location" in data
    assert "highest_exposure_corridors" in data
    print("  [PASS] Summary endpoint verified.")


def test_8_geojson_endpoint():
    print("Test 8: GeoJSON endpoint (/api/impact/geojson)...")
    res = client.get("/api/impact/geojson?top_n_hotspots=5")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) > 0

    feature_types = {f["geometry"]["type"] for f in data["features"]}
    assert "Point" in feature_types
    assert "Polygon" in feature_types
    assert "LineString" in feature_types
    print(f"  [PASS] GeoJSON endpoint verified with geometries: {feature_types}.")


def test_9_invalid_location():
    print("Test 9: Invalid location ID handling (404)...")
    res1 = client.get("/api/locations/9999999/impact")
    assert res1.status_code == 404, f"Expected 404, got {res1.status_code}"

    res2 = client.get("/api/impact/areas/9999999")
    assert res2.status_code == 404, f"Expected 404, got {res2.status_code}"

    res3 = client.get("/api/locations/9999999")
    assert res3.status_code == 404, f"Expected 404, got {res3.status_code}"
    print("  [PASS] 404 error handling verified for nonexistent IDs.")


def test_10_invalid_parameters():
    print("Test 10: Invalid parameters handling (400 / 422)...")
    # Coordinates out of bounds
    res1 = client.get(
        "/api/impact/route?start_lat=120.0&start_lon=78.48&end_lat=17.42&end_lon=78.48"
    )
    assert res1.status_code in [400, 422], f"Expected 400 or 422, got {res1.status_code}"

    # Negative radius
    res2 = client.get("/api/impact/areas/3353?radius_km=-5")
    assert res2.status_code in [400, 422], f"Expected 400 or 422, got {res2.status_code}"
    print("  [PASS] Parameter validation verified.")


def test_11_nan_infinity_validation():
    print("Test 11: Global NaN/Infinity validation across all endpoints...")
    endpoints = [
        "/",
        "/api/stats",
        "/api/locations",
        "/api/top-risk?limit=10",
        "/api/locations/3353",
        "/api/locations/3353/explanation",
        "/api/locations/3353/impact",
        "/api/impact/areas/3353?radius_km=1.5&limit=25",
        "/api/impact/route?start_lat=17.385&start_lon=78.4867&end_lat=17.42&end_lon=78.48",
        "/api/impact/routes?limit=5",
        "/api/impact/summary",
        "/api/impact/geojson?top_n_hotspots=5",
        "/api/localities",
    ]

    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 200, f"Endpoint {ep} failed with {res.status_code}: {res.text}"
        data = res.json()
        assert_no_nan_or_inf(data, path=ep)
    print("  [PASS] No NaN or Infinity found across all endpoints.")


def test_12_existing_endpoints_unbroken():
    print("Test 12: Verifying existing endpoints are preserved and fully functional...")
    # Root
    r = client.get("/").json()
    assert r["project"] == "FLOWSIGHT"

    # Stats
    stats = client.get("/api/stats").json()
    assert stats["total_locations"] == 1013
    assert "risk_distribution" in stats
    assert stats["highest_risk_score"] > 80.0

    # Locations
    locs = client.get("/api/locations").json()
    assert locs["count"] == 1013

    # Top risk
    top = client.get("/api/top-risk?limit=5").json()
    assert top["count"] == 5
    assert top["locations"][0]["priority"] == 1

    # Single location
    loc = client.get("/api/locations/3353").json()
    assert loc["location_id"] == 3353

    # Explanation
    exp = client.get("/api/locations/3353/explanation").json()
    assert exp["location_id"] == 3353
    assert "strongest_factor" in exp
    assert "explanation" in exp

    # Localities
    localities = client.get("/api/localities").json()
    assert isinstance(localities, dict)
    print("  [PASS] All existing endpoints preserved and fully functional.")


if __name__ == "__main__":
    print("==================================================")
    print("RUNNING FLOWSIGHT SPATIAL IMPACT TEST SUITE")
    print("==================================================")
    test_1_haversine()
    test_2_radius_search()
    test_3_location_impact_endpoint()
    test_4_areas_endpoint()
    test_5_route_endpoint()
    test_6_routes_ranking_endpoint()
    test_7_summary_endpoint()
    test_8_geojson_endpoint()
    test_9_invalid_location()
    test_10_invalid_parameters()
    test_11_nan_infinity_validation()
    test_12_existing_endpoints_unbroken()
    print("==================================================")
    print("ALL 12 TEST SUITES PASSED SUCCESSFULLY!")
    print("==================================================")
