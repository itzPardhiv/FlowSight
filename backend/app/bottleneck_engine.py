from pathlib import Path
from typing import Any, Dict, List, Optional
import math
import numpy as np
import pandas as pd

from .geo_utils import (
    haversine_distance,
    distance_matrix,
    generate_circle_polygon,
)
from .impact_engine import impact_engine, classify_exposure

BOTTLENECK_DISCLAIMER = (
    "Potential Drainage Bottleneck Zone: Analytical spatial clustering of elevated risk signals "
    "and transit corridor convergence. This model indicates where multiple surface runoff and "
    "exposure signals concentrate; it does not indicate confirmed subsurface pipe blockages, "
    "structural drainage failure, or surveyed municipal pipe conditions."
)


class BottleneckEngine:
    """
    Drainage Bottleneck & Spatial Risk Convergence Engine for FLOWSIGHT.
    Groups proximate high-risk locations and intersecting corridors into
    analytical convergence zones.
    """

    def __init__(self):
        self._cached_clusters: Optional[List[Dict[str, Any]]] = None

    def detect_bottlenecks(
        self,
        min_risk: float = 60.0,
        radius_km: float = 1.5,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Detects and ranks potential drainage bottleneck zones across the FLOWSIGHT grid.
        Uses greedy peak-density clustering on locations with risk >= min_risk.
        """
        df = impact_engine.get_df()
        high_risk_df = df[df["risk_score"] >= min_risk].copy()

        if high_risk_df.empty:
            return []

        # Sort seeds by risk_score descending
        high_risk_df = high_risk_df.sort_values("risk_score", ascending=False).reset_index(drop=True)

        coords = high_risk_df[["latitude", "longitude"]].values
        n_pts = len(high_risk_df)
        dist_mat = distance_matrix(coords, coords)

        assigned = np.zeros(n_pts, dtype=bool)
        clusters_raw = []

        for i in range(n_pts):
            if assigned[i]:
                continue

            # Find all high-risk points within radius_km
            in_cluster_indices = np.where((dist_mat[i] <= radius_km) & (~assigned))[0]

            # Mark as assigned
            assigned[in_cluster_indices] = True

            member_df = high_risk_df.iloc[in_cluster_indices]
            clusters_raw.append(member_df)

        # Corridors for route exposure calculation
        corridors = impact_engine.get_ranked_corridors(limit=15)

        # Locality mapping
        localities_file = Path(__file__).resolve().parent / "localities.json"
        locality_map: Dict[str, str] = {}
        if localities_file.exists():
            import json
            with open(localities_file, "r", encoding="utf-8") as f:
                locality_map = json.load(f)

        bottlenecks = []
        for cluster_members in clusters_raw:
            member_count = len(cluster_members)

            # Weighted centroid
            weights = cluster_members["risk_score"].values
            total_weight = float(weights.sum()) if weights.sum() > 0 else 1.0
            c_lat = float(np.sum(cluster_members["latitude"].values * weights) / total_weight)
            c_lon = float(np.sum(cluster_members["longitude"].values * weights) / total_weight)

            # Calculate cluster radius: max distance from centroid + 0.25 km buffer
            member_coords = cluster_members[["latitude", "longitude"]].values
            c_pt = np.array([[c_lat, c_lon]])
            dists_to_c = distance_matrix(c_pt, member_coords)[0]
            max_d = float(np.max(dists_to_c)) if len(dists_to_c) > 0 else 0.25
            c_radius = max(0.5, round(max_d + 0.25, 2))

            avg_risk = round(float(cluster_members["risk_score"].mean()), 2)
            max_risk = round(float(cluster_members["risk_score"].max()), 2)

            # Count nearby risk corridors
            nearby_routes = []
            for corr in corridors:
                d_start = haversine_distance(c_lat, c_lon, corr["start"]["latitude"], corr["start"]["longitude"])
                d_end = haversine_distance(c_lat, c_lon, corr["end"]["latitude"], corr["end"]["longitude"])
                if d_start <= (c_radius + 0.5) or d_end <= (c_radius + 0.5):
                    nearby_routes.append(
                        {
                            "corridor_id": corr["corridor_id"],
                            "name": corr["name"],
                            "average_risk_score": corr["average_risk_score"],
                            "exposure_level": corr["exposure_level"],
                            "distance_to_center_km": round(min(d_start, d_end), 2),
                        }
                    )

            nearby_route_count = len(nearby_routes)

            # Area estimate: 0.25 km² per grid cell
            affected_area = round(float(member_count * 0.25), 2)

            # Bottleneck score formula:
            # Base risk: 40% avg + 25% max
            # Concentration bonus: up to 20 pts (2.0 pts per point)
            # Route convergence bonus: up to 15 pts (3.0 pts per corridor)
            base_risk = 0.40 * avg_risk + 0.25 * max_risk
            conc_bonus = min(20.0, member_count * 2.0)
            route_bonus = min(15.0, nearby_route_count * 3.0)
            raw_score = base_risk + conc_bonus + route_bonus
            bottleneck_score = min(100.0, round(float(raw_score), 2))

            risk_level = "Very High" if bottleneck_score >= 75.0 else ("High" if bottleneck_score >= 60.0 else "Moderate")

            # Determine nearest verified locality or peak location
            peak_loc = cluster_members.sort_values("risk_score", ascending=False).iloc[0]
            peak_id = int(peak_loc["location_id"])

            # Find nearest verified locality name
            locality_label = locality_map.get(str(peak_id), f"Location {peak_id}")
            for _, m_row in cluster_members.iterrows():
                m_id = str(int(m_row["location_id"]))
                if m_id in locality_map:
                    locality_label = locality_map[m_id]
                    break

            # Contributing locations summary
            contributing = []
            for _, m_row in cluster_members.sort_values("risk_score", ascending=False).iterrows():
                m_id_int = int(m_row["location_id"])
                contributing.append(
                    {
                        "location_id": m_id_int,
                        "locality": locality_map.get(str(m_id_int), f"Location {m_id_int}"),
                        "latitude": float(m_row["latitude"]),
                        "longitude": float(m_row["longitude"]),
                        "risk_score": float(m_row["risk_score"]),
                        "risk_level": str(m_row["risk_level"]),
                        "elevation": float(m_row.get("elevation", 0.0)),
                        "slope": float(m_row.get("slope", 0.0)),
                        "built_up": float(m_row.get("built_up", 0.0)),
                        "road_density": float(m_row.get("road_density", 0.0)),
                    }
                )

            polygon_coords = generate_circle_polygon(c_lat, c_lon, c_radius, num_points=24)

            explanation = (
                f"Spatial convergence of {member_count} high-risk analysis locations "
                f"(average risk: {avg_risk:.1f}, peak: {max_risk:.1f}) and {nearby_route_count} proximate "
                f"transit corridors within an estimated {c_radius:.1f} km influence zone."
            )

            rec_inspection = (
                f"Field Inspection Priority: Deploy drainage and stormwater assessment teams "
                f"to inspect culverts, surface inlets, and trunk nala discharge points across "
                f"{locality_label} ({member_count} converging risk points)."
            )

            bottlenecks.append(
                {
                    "bottleneck_id": "",  # Assigned after ranking
                    "name": "",           # Assigned after ranking
                    "locality": locality_label,
                    "center_latitude": round(c_lat, 6),
                    "center_longitude": round(c_lon, 6),
                    "radius_km": c_radius,
                    "number_of_high_risk_locations": member_count,
                    "average_risk": avg_risk,
                    "maximum_risk": max_risk,
                    "nearby_route_count": nearby_route_count,
                    "affected_area_estimate": affected_area,
                    "bottleneck_score": bottleneck_score,
                    "risk_level": risk_level,
                    "priority": 0,
                    "contributing_locations": contributing,
                    "nearby_routes": nearby_routes,
                    "polygon_coordinates": polygon_coords,
                    "explanation": explanation,
                    "recommended_action": rec_inspection,
                    "disclaimer": BOTTLENECK_DISCLAIMER,
                }
            )

        # Sort by bottleneck_score descending
        bottlenecks.sort(key=lambda b: b["bottleneck_score"], reverse=True)

        for rank, b in enumerate(bottlenecks, start=1):
            b["bottleneck_id"] = f"bottleneck_{rank}"
            b["name"] = f"Potential Bottleneck Zone #{rank} — {b['locality']}"
            b["priority"] = rank

        self._cached_clusters = bottlenecks
        return bottlenecks[:limit]

    def get_bottleneck_by_id(self, bottleneck_id: str) -> Dict[str, Any]:
        """Returns details for a specific bottleneck cluster."""
        all_clusters = self.detect_bottlenecks(limit=50)
        for b in all_clusters:
            if b["bottleneck_id"] == bottleneck_id:
                return b
        raise KeyError(f"Bottleneck '{bottleneck_id}' not found")


# Global singleton
bottleneck_engine = BottleneckEngine()
