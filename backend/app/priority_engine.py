from pathlib import Path
from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd

from .geo_utils import haversine_distance
from .impact_engine import impact_engine, classify_exposure, DISCLAIMER_TEXT
from .bottleneck_engine import bottleneck_engine
from .scenario_engine import scenario_engine

PRIORITY_DISCLAIMER = (
    "Action Priority Index: Transparent decision-support metric combining baseline risk, "
    "spatial exposure footprint, corridor convergence, bottleneck concentration, and "
    "scenario stress sensitivity. Inundation is modeled as risk exposure; flooding is not "
    "guaranteed."
)

PRIORITY_WEIGHTS = {
    "risk_score": 0.35,
    "exposure_radius": 0.15,
    "affected_area": 0.15,
    "route_exposure": 0.15,
    "bottleneck_concentration": 0.10,
    "scenario_sensitivity": 0.10,
}


class PriorityEngine:
    """
    Action Priority Engine for FLOWSIGHT.
    Computes a transparent, reproducible multi-criteria Priority Index
    guiding municipal inspection and field crew dispatch.
    """

    def __init__(self):
        self._cached_priorities: Dict[str, List[Dict[str, Any]]] = {}

    def compute_priorities(
        self,
        scenario_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Computes the Priority Index for candidate priority locations across Hyderabad.
        Focuses on top baseline hotspots and elevated clusters to provide actionable ranking.
        """
        cache_key = f"{scenario_id or 'default'}_{limit}"
        if cache_key in self._cached_priorities:
            return self._cached_priorities[cache_key]

        df = impact_engine.get_df()
        # Candidate set: top 50 risk locations for high-resolution priority evaluation
        candidates = df.sort_values("risk_score", ascending=False).head(50).copy()

        # Scenario evaluation for sensitivity delta
        scen_id = scenario_id or "heavy_downpour_120"
        try:
            scen_df = scenario_engine.evaluate_scenario(scen_id)
            scen_delta_map = dict(zip(scen_df["location_id"], scen_df["risk_delta"]))
        except Exception:
            scen_delta_map = {row["location_id"]: 4.0 for _, row in candidates.iterrows()}

        # Bottlenecks for spatial concentration score
        bottlenecks = bottleneck_engine.detect_bottlenecks(limit=15)

        # Ranked corridors for route exposure
        corridors = impact_engine.get_ranked_corridors(limit=15)

        # Locality mapping
        localities_file = Path(__file__).resolve().parent / "localities.json"
        locality_map: Dict[str, str] = {}
        if localities_file.exists():
            import json
            with open(localities_file, "r", encoding="utf-8") as f:
                locality_map = json.load(f)

        records = []
        for _, row in candidates.iterrows():
            loc_id = int(row["location_id"])
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            base_risk = float(row["risk_score"])
            risk_level = str(row["risk_level"])

            # 1. Recommended exposure radius & affected area
            bands = impact_engine.calculate_radius_bands(lat, lon)
            rec_radius, _ = impact_engine.derive_recommended_radius(bands, base_risk)
            affected_nearby = impact_engine.get_affected_areas(loc_id, radius_km=rec_radius, limit=20)
            affected_count = affected_nearby["count"]
            affected_area_km2 = round(affected_count * 0.25, 2)

            # 2. Exposed route count (corridors within 2.0 km)
            nearby_routes = 0
            for c in corridors:
                d_s = haversine_distance(lat, lon, c["start"]["latitude"], c["start"]["longitude"])
                d_e = haversine_distance(lat, lon, c["end"]["latitude"], c["end"]["longitude"])
                if d_s <= 2.0 or d_e <= 2.0:
                    nearby_routes += 1

            # 3. Bottleneck concentration score
            b_score = 0.0
            for b in bottlenecks:
                d_b = haversine_distance(lat, lon, b["center_latitude"], b["center_longitude"])
                if d_b <= (b["radius_km"] + 0.3):
                    b_score = max(b_score, b["bottleneck_score"])

            # 4. Scenario sensitivity delta
            delta = float(scen_delta_map.get(loc_id, 3.5))

            # Normalized components (0 to 100)
            c_risk = base_risk
            c_radius = min(100.0, (rec_radius / 3.0) * 100.0)
            c_affected = min(100.0, affected_count * 10.0)
            c_routes = min(100.0, nearby_routes * 33.33)
            c_bottleneck = b_score
            c_scenario = min(100.0, delta * 12.5)

            # Composite Priority Index
            p_index = round(
                PRIORITY_WEIGHTS["risk_score"] * c_risk
                + PRIORITY_WEIGHTS["exposure_radius"] * c_radius
                + PRIORITY_WEIGHTS["affected_area"] * c_affected
                + PRIORITY_WEIGHTS["route_exposure"] * c_routes
                + PRIORITY_WEIGHTS["bottleneck_concentration"] * c_bottleneck
                + PRIORITY_WEIGHTS["scenario_sensitivity"] * c_scenario,
                2,
            )

            locality_name = locality_map.get(str(loc_id), f"Location {loc_id}")

            # Transparent reason
            explanation = (
                f"Elevated baseline risk ({base_risk:.1f}/100) with an estimated {rec_radius:.1f} km "
                f"exposure footprint ({affected_count} proximate catchments, ~{affected_area_km2:.2f} km²), "
                f"{nearby_routes} nearby risk transit corridors, and a convergence bottleneck score of {b_score:.1f}."
            )

            # Actionable field inspection text
            if p_index >= 75.0:
                rec_action = (
                    f"Immediate Priority Inspection: Inspect main storm drains, culvert inlets, "
                    f"and road underpasses in {locality_name}. Position mobile dewatering pumps "
                    f"ahead of severe rainfall."
                )
            elif p_index >= 60.0:
                rec_action = (
                    f"High Priority Field Check: Verify unobstructed roadside drainage channels "
                    f"and clear localized silt traps across {locality_name} within the 24h operational window."
                )
            else:
                rec_action = (
                    f"Preventive Monitoring: Conduct scheduled runoff path clearing and surface drain "
                    f"maintenance in {locality_name}."
                )

            records.append(
                {
                    "priority_index": p_index,
                    "priority_rank": 0,  # Assigned after sorting
                    "location_id": loc_id,
                    "locality": locality_name,
                    "latitude": lat,
                    "longitude": lon,
                    "risk_score": base_risk,
                    "risk_level": risk_level,
                    "affected_area": affected_area_km2,
                    "exposure_radius": rec_radius,
                    "exposed_route_count": nearby_routes,
                    "bottleneck_score": b_score,
                    "scenario_sensitivity": delta,
                    "recommended_action": rec_action,
                    "explanation": explanation,
                    "component_scores": {
                        "risk_score_component": round(c_risk, 2),
                        "exposure_radius_component": round(c_radius, 2),
                        "affected_area_component": round(c_affected, 2),
                        "route_exposure_component": round(c_routes, 2),
                        "bottleneck_component": round(c_bottleneck, 2),
                        "scenario_sensitivity_component": round(c_scenario, 2),
                    },
                    "weights": PRIORITY_WEIGHTS,
                    "disclaimer": PRIORITY_DISCLAIMER,
                }
            )

        # Sort by priority_index descending
        records.sort(key=lambda r: r["priority_index"], reverse=True)

        for rank, r in enumerate(records, start=1):
            r["priority_rank"] = rank

        self._cached_priorities[cache_key] = records
        return records[:limit]

    def get_priority_by_location_id(
        self,
        location_id: int,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns the full priority breakdown for a specific location."""
        priorities = self.compute_priorities(scenario_id=scenario_id, limit=50)
        for p in priorities:
            if p["location_id"] == location_id:
                return p

        # If not in top 50, compute on-demand for this specific location
        df = impact_engine.get_df()
        match = df[df["location_id"] == location_id]
        if match.empty:
            raise KeyError(f"Location {location_id} not found")

        row = match.iloc[0]
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        base_risk = float(row["risk_score"])
        risk_level = str(row["risk_level"])

        bands = impact_engine.calculate_radius_bands(lat, lon)
        rec_radius, _ = impact_engine.derive_recommended_radius(bands, base_risk)
        affected_nearby = impact_engine.get_affected_areas(location_id, radius_km=rec_radius, limit=20)
        affected_count = affected_nearby["count"]
        affected_area_km2 = round(affected_count * 0.25, 2)

        corridors = impact_engine.get_ranked_corridors(limit=15)
        nearby_routes = sum(
            1
            for c in corridors
            if haversine_distance(lat, lon, c["start"]["latitude"], c["start"]["longitude"]) <= 2.0
            or haversine_distance(lat, lon, c["end"]["latitude"], c["end"]["longitude"]) <= 2.0
        )

        bottlenecks = bottleneck_engine.detect_bottlenecks(limit=15)
        b_score = 0.0
        for b in bottlenecks:
            if haversine_distance(lat, lon, b["center_latitude"], b["center_longitude"]) <= (b["radius_km"] + 0.3):
                b_score = max(b_score, b["bottleneck_score"])

        scen_id = scenario_id or "heavy_downpour_120"
        try:
            scen_df = scenario_engine.evaluate_scenario(scen_id)
            delta = float(scen_df[scen_df["location_id"] == location_id]["risk_delta"].iloc[0])
        except Exception:
            delta = 3.5

        c_risk = base_risk
        c_radius = min(100.0, (rec_radius / 3.0) * 100.0)
        c_affected = min(100.0, affected_count * 10.0)
        c_routes = min(100.0, nearby_routes * 33.33)
        c_bottleneck = b_score
        c_scenario = min(100.0, delta * 12.5)

        p_index = round(
            PRIORITY_WEIGHTS["risk_score"] * c_risk
            + PRIORITY_WEIGHTS["exposure_radius"] * c_radius
            + PRIORITY_WEIGHTS["affected_area"] * c_affected
            + PRIORITY_WEIGHTS["route_exposure"] * c_routes
            + PRIORITY_WEIGHTS["bottleneck_concentration"] * c_bottleneck
            + PRIORITY_WEIGHTS["scenario_sensitivity"] * c_scenario,
            2,
        )

        localities_file = Path(__file__).resolve().parent / "localities.json"
        locality_map: Dict[str, str] = {}
        if localities_file.exists():
            import json
            with open(localities_file, "r", encoding="utf-8") as f:
                locality_map = json.load(f)

        locality_name = locality_map.get(str(location_id), f"Location {location_id}")

        return {
            "priority_index": p_index,
            "priority_rank": int(row.get("priority", 999)),
            "location_id": location_id,
            "locality": locality_name,
            "latitude": lat,
            "longitude": lon,
            "risk_score": base_risk,
            "risk_level": risk_level,
            "affected_area": affected_area_km2,
            "exposure_radius": rec_radius,
            "exposed_route_count": nearby_routes,
            "bottleneck_score": b_score,
            "scenario_sensitivity": delta,
            "recommended_action": (
                f"Routine Inspection: Maintain catchment monitoring and local drain inlets in {locality_name}."
            ),
            "explanation": (
                f"Location {location_id} has baseline risk {base_risk:.1f}/100, "
                f"estimated exposure radius {rec_radius:.1f} km, and {nearby_routes} proximate transit routes."
            ),
            "component_scores": {
                "risk_score_component": round(c_risk, 2),
                "exposure_radius_component": round(c_radius, 2),
                "affected_area_component": round(c_affected, 2),
                "route_exposure_component": round(c_routes, 2),
                "bottleneck_component": round(c_bottleneck, 2),
                "scenario_sensitivity_component": round(c_scenario, 2),
            },
            "weights": PRIORITY_WEIGHTS,
            "disclaimer": PRIORITY_DISCLAIMER,
        }


# Global singleton
priority_engine = PriorityEngine()
