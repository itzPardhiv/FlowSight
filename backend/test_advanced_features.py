import json
import math
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app

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


def test_1_scenarios_catalog():
    print("Test 1: Scenarios catalog endpoint (/api/scenarios)...")
    res = client.get("/api/scenarios")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert "count" in data
    assert "scenarios" in data
    assert data["count"] >= 3
    assert len(data["scenarios"]) == data["count"]

    first = data["scenarios"][0]
    for key in [
        "scenario_id",
        "name",
        "type",
        "description",
        "rainfall_multiplier",
        "affected_location_count",
        "average_risk",
        "maximum_risk",
        "risk_distribution",
    ]:
        assert key in first, f"Missing key '{key}' in scenario record"

    assert "Model Scenario" in first["type"] or "Event Replay" in first["type"]
    print("  [PASS] Scenarios catalog endpoint verified.")


def test_2_scenario_details():
    print("Test 2: Scenario details endpoint (/api/scenarios/{scenario_id})...")
    res = client.get("/api/scenarios/heavy_downpour_120")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert data["scenario_id"] == "heavy_downpour_120"
    assert "risk_distribution" in data
    assert "Very High" in data["risk_distribution"]
    assert "top_affected_locations" in data
    assert len(data["top_affected_locations"]) > 0

    first_loc = data["top_affected_locations"][0]
    assert "baseline_risk_score" in first_loc
    assert "scenario_risk_score" in first_loc
    assert "risk_delta" in first_loc

    # 404 test for non-existent scenario
    res_404 = client.get("/api/scenarios/non_existent_scenario_xyz")
    assert res_404.status_code == 404
    print("  [PASS] Scenario details endpoint & 404 verified.")


def test_3_scenario_compare():
    print("Test 3: Scenario compare endpoint (/api/scenarios/{scenario_id}/compare)...")
    res = client.get("/api/scenarios/heavy_downpour_120/compare")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert "baseline_average_risk" in data
    assert "scenario_average_risk" in data
    assert "baseline_maximum_risk" in data
    assert "scenario_maximum_risk" in data
    assert "locations_whose_risk_level_increased" in data
    assert "newly_elevated_hotspots" in data
    assert "top_changed_locations" in data

    assert data["scenario_average_risk"] >= data["baseline_average_risk"]
    assert data["locations_whose_risk_level_increased"] >= 0

    # Test October 2020 Replay
    res_2020 = client.get("/api/scenarios/historical_replay_2020_model/compare")
    assert res_2020.status_code == 200
    data_2020 = res_2020.json()
    assert_no_nan_or_inf(data_2020)
    assert "October 2020 Synoptic Rain Pattern" in data_2020["name"]

    # 404 test
    res_404 = client.get("/api/scenarios/invalid_scen/compare")
    assert res_404.status_code == 404
    print("  [PASS] Scenario compare endpoint & 404 verified.")


def test_4_bottlenecks_endpoint():
    print("Test 4: Drainage bottlenecks endpoint (/api/impact/bottlenecks)...")
    res = client.get("/api/impact/bottlenecks?min_risk=60.0&radius=1.5&limit=10")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert "count" in data
    assert "bottlenecks" in data
    assert len(data["bottlenecks"]) <= 10
    assert data["count"] > 0

    b1 = data["bottlenecks"][0]
    for key in [
        "bottleneck_id",
        "center_latitude",
        "center_longitude",
        "radius_km",
        "number_of_high_risk_locations",
        "average_risk",
        "maximum_risk",
        "nearby_route_count",
        "affected_area_estimate",
        "bottleneck_score",
        "risk_level",
        "priority",
        "locality",
    ]:
        assert key in b1, f"Missing key '{key}' in bottleneck record"

    assert b1["bottleneck_score"] > 0.0
    assert b1["priority"] == 1
    assert "disclaimer" in data

    # 422 test for invalid parameter
    res_422 = client.get("/api/impact/bottlenecks?min_risk=200.0")
    assert res_422.status_code == 422
    print("  [PASS] Bottlenecks endpoint & validation verified.")


def test_5_bottleneck_details():
    print("Test 5: Bottleneck detail endpoint (/api/impact/bottlenecks/{id})...")
    # First get the first bottleneck ID
    list_res = client.get("/api/impact/bottlenecks?limit=1")
    b_id = list_res.json()["bottlenecks"][0]["bottleneck_id"]

    res = client.get(f"/api/impact/bottlenecks/{b_id}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert data["bottleneck_id"] == b_id
    assert "contributing_locations" in data
    assert "polygon_coordinates" in data
    assert "recommended_action" in data
    assert len(data["contributing_locations"]) > 0

    # 404 test
    res_404 = client.get("/api/impact/bottlenecks/non_existent_cluster_999")
    assert res_404.status_code == 404
    print("  [PASS] Bottleneck detail & 404 verified.")


def test_6_priority_endpoint():
    print("Test 6: Priority endpoint (/api/priority)...")
    res = client.get("/api/priority?limit=10")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert "priorities" in data
    assert len(data["priorities"]) == 10

    p1 = data["priorities"][0]
    for key in [
        "priority_index",
        "priority_rank",
        "location_id",
        "locality",
        "latitude",
        "longitude",
        "risk_score",
        "risk_level",
        "affected_area",
        "exposure_radius",
        "exposed_route_count",
        "bottleneck_score",
        "scenario_sensitivity",
        "recommended_action",
        "explanation",
        "component_scores",
    ]:
        assert key in p1, f"Missing key '{key}' in priority record"

    assert p1["priority_rank"] == 1
    # Check that list is sorted by priority_index descending
    indices = [p["priority_index"] for p in data["priorities"]]
    assert indices == sorted(indices, reverse=True), "Priorities must be sorted by priority_index descending"

    # Test with scenario_id parameter
    res_scen = client.get("/api/priority?limit=5&scenario_id=extreme_monsoon_150")
    assert res_scen.status_code == 200
    assert len(res_scen.json()["priorities"]) == 5
    print("  [PASS] Priority endpoint verified.")


def test_7_priority_detail_endpoint():
    print("Test 7: Priority detail endpoint (/api/priority/{location_id})...")
    res = client.get("/api/priority/3353")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert_no_nan_or_inf(data)

    assert data["location_id"] == 3353
    assert data["locality"] == "Hussaini Alam"
    assert "priority_index" in data
    assert "component_scores" in data
    assert "weights" in data
    assert "recommended_action" in data

    # 404 test
    res_404 = client.get("/api/priority/999999")
    assert res_404.status_code == 404
    print("  [PASS] Priority detail & 404 verified.")


def test_8_existing_endpoints_preserved():
    print("Test 8: Re-verifying all original endpoints...")
    endpoints = [
        "/",
        "/api/stats",
        "/api/locations",
        "/api/top-risk",
        "/api/locations/3353",
        "/api/locations/3353/explanation",
        "/api/localities",
        "/api/impact/areas/3353?radius_km=1.0",
        "/api/impact/route?start_lat=17.38&start_lon=78.48&end_lat=17.41&end_lon=78.48",
        "/api/impact/routes?limit=5",
        "/api/impact/summary",
        "/api/impact/geojson?top_n_hotspots=5",
        "/api/locations/3353/impact",
    ]

    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 200, f"Endpoint {ep} returned {res.status_code}"
        data = res.json()
        assert_no_nan_or_inf(data, path=ep)

    print("  [PASS] All existing endpoints verified without regression.")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING FLOWSIGHT ADVANCED FEATURES TEST SUITE")
    print("=" * 60)
    test_1_scenarios_catalog()
    test_2_scenario_details()
    test_3_scenario_compare()
    test_4_bottlenecks_endpoint()
    test_5_bottleneck_details()
    test_6_priority_endpoint()
    test_7_priority_detail_endpoint()
    test_8_existing_endpoints_preserved()
    print("=" * 60)
    print("ALL 8 ADVANCED FEATURE TEST SUITES PASSED SUCCESSFULLY!")
    print("=" * 60)
