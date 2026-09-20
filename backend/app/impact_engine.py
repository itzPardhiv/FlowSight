from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd

from .geo_utils import (
    haversine_distance,
    distance_matrix,
    interpolate_route,
    points_within_radius,
    nearest_location,
    generate_circle_polygon,
)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "locations_features.csv"

DISCLAIMER_TEXT = (
    "FLOWSIGHT estimates spatial exposure from the current risk model. "
    "It does not represent observed flood extent, real-time sensor measurements, "
    "or guaranteed road flooding."
)

DEFAULT_RADIUS_BANDS = [0.5, 1.0, 2.0, 3.0, 5.0]
GRID_CELL_AREA_KM2 = 0.25  # ~500m x 500m grid cell approximation


def classify_exposure(risk_score: float) -> str:
    """
    Classify risk score into analytical exposure categories.
    risk_score >= 75 -> Very High Exposure
    risk_score >= 60 -> High Exposure
    risk_score >= 40 -> Moderate Exposure
    otherwise        -> Low Exposure
    """
    if risk_score >= 75.0:
        return "Very High Exposure"
    elif risk_score >= 60.0:
        return "High Exposure"
    elif risk_score >= 40.0:
        return "Moderate Exposure"
    else:
        return "Low Exposure"


class ImpactEngine:
    """
    Spatial Impact & Route Exposure Engine for FLOWSIGHT.
    Computes spatial risk influence, route exposure, corridors,
    and GeoJSON representations based on existing model data.
    """

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or DATA_FILE
        self._df: Optional[pd.DataFrame] = None
        self._cached_corridors: Optional[List[Dict[str, Any]]] = None

    def get_df(self) -> pd.DataFrame:
        if self._df is None:
            if not self.data_path.exists():
                raise FileNotFoundError(f"Dataset not found: {self.data_path}")
            df = pd.read_csv(self.data_path)
            # Ensure proper types and replace any NaN/inf values
            df = df.fillna(0.0)
            df["location_id"] = df["location_id"].astype(int)
            df["latitude"] = df["latitude"].astype(float)
            df["longitude"] = df["longitude"].astype(float)
            df["risk_score"] = df["risk_score"].astype(float)
            df["priority"] = df["priority"].astype(int)
            if "exposure_level" not in df.columns:
                df["exposure_level"] = df["risk_score"].apply(classify_exposure)
            self._df = df
        return self._df

    def get_location_by_id(self, location_id: int) -> Dict[str, Any]:
        df = self.get_df()
        match = df[df["location_id"] == location_id]
        if match.empty:
            raise KeyError(f"Location ID {location_id} not found")
        row = match.iloc[0]
        return {
            "location_id": int(row["location_id"]),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "risk_score": float(row["risk_score"]),
            "risk_level": str(row["risk_level"]),
            "priority": int(row["priority"]),
            "elevation": float(row.get("elevation", 0.0)),
            "slope": float(row.get("slope", 0.0)),
            "built_up": float(row.get("built_up", 0.0)),
            "rainfall": float(row.get("rainfall", 0.0)),
            "road_density": float(row.get("road_density", 0.0)),
            "exposure_level": classify_exposure(float(row["risk_score"])),
        }

    # ==========================================
    # FEATURE 1: HOTSPOT IMPACT RADIUS
    # ==========================================
    def calculate_radius_bands(
        self,
        center_lat: float,
        center_lon: float,
        bands: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculates risk intensity statistics across configurable distance bands.
        """
        bands = bands or DEFAULT_RADIUS_BANDS
        df = self.get_df()

        coords = df[["latitude", "longitude"]].values
        center = np.array([[center_lat, center_lon]])
        distances = distance_matrix(center, coords)[0]

        df_dist = df.copy()
        df_dist["dist_km"] = distances

        band_results = []
        for radius in sorted(bands):
            subset = df_dist[df_dist["dist_km"] <= radius]
            count = len(subset)

            if count > 0:
                avg_risk = round(float(subset["risk_score"].mean()), 2)
                max_risk = round(float(subset["risk_score"].max()), 2)
                high_risk_count = int((subset["risk_score"] >= 60.0).sum())
                very_high_risk_count = int((subset["risk_score"] >= 75.0).sum())
                exposure_level = classify_exposure(avg_risk)
            else:
                avg_risk = 0.0
                max_risk = 0.0
                high_risk_count = 0
                very_high_risk_count = 0
                exposure_level = "Low Exposure"

            band_results.append(
                {
                    "radius_km": float(radius),
                    "number_of_locations": count,
                    "average_risk_score": avg_risk,
                    "maximum_risk_score": max_risk,
                    "high_risk_locations": high_risk_count,
                    "very_high_risk_locations": very_high_risk_count,
                    "estimated_exposure_level": exposure_level,
                }
            )

        return band_results

    def derive_recommended_radius(
        self,
        bands: List[Dict[str, Any]],
        origin_risk_score: float,
    ) -> Tuple[float, str]:
        """
        Derives an analytical recommended risk influence radius based on
        surrounding risk distribution decay and high-risk point clustering.
        """
        # Search from largest to smallest band where significant elevated exposure exists
        # If origin is high/very high, find the band where average risk is elevated
        # or where very high / high risk density is maintained
        recommended = 0.5
        reason = "Model identifies localized risk influence concentrated within 0.5 km."

        for band in bands:
            r = band["radius_km"]
            avg = band["average_risk_score"]
            vh_count = band["very_high_risk_locations"]
            h_count = band["high_risk_locations"]
            tot = band["number_of_locations"]

            if tot > 0:
                high_ratio = (vh_count + h_count) / tot
                if avg >= 60.0 or (high_ratio >= 0.25 and (vh_count + h_count) >= 2):
                    recommended = r
                    reason = (
                        f"Model identifies elevated risk influence extending to {r} km "
                        f"with {h_count + vh_count} elevated risk points (average risk: {avg:.2f})."
                    )

        return float(recommended), reason

    # ==========================================
    # FEATURE 2: AFFECTED AREAS
    # ==========================================
    def get_affected_areas(
        self,
        location_id: int,
        radius_km: float = 1.0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Identifies surrounding spatial locations within radius_km,
        sorted by risk_score descending and distance ascending.
        """
        origin = self.get_location_by_id(location_id)
        df = self.get_df()

        surrounding = points_within_radius(
            df,
            origin["latitude"],
            origin["longitude"],
            radius_km,
        )

        # Exclude the origin point itself if desired, or keep it.
        # Keeping surrounding points with distance
        surrounding = surrounding.sort_values(
            by=["risk_score", "distance_km"],
            ascending=[False, True],
        ).head(limit)

        records = []
        for _, row in surrounding.iterrows():
            records.append(
                {
                    "location_id": int(row["location_id"]),
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "distance_km": round(float(row["distance_km"]), 3),
                    "risk_score": float(row["risk_score"]),
                    "risk_level": str(row["risk_level"]),
                    "priority": int(row["priority"]),
                    "exposure_level": classify_exposure(float(row["risk_score"])),
                }
            )

        return {
            "origin_location_id": location_id,
            "origin_coordinates": {
                "latitude": origin["latitude"],
                "longitude": origin["longitude"],
            },
            "radius_km": float(radius_km),
            "count": len(records),
            "disclaimer": DISCLAIMER_TEXT,
            "locations": records,
        }

    # ==========================================
    # FEATURE 3: ROUTE EXPOSURE
    # ==========================================
    def analyze_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        corridor_km: float = 0.25,
        samples: int = 50,
    ) -> Dict[str, Any]:
        """
        Analyzes exposure along a geodesic corridor between start and end coordinates.
        """
        df = self.get_df()
        interpolated = interpolate_route(
            start_lat, start_lon, end_lat, end_lon, samples=samples
        )
        total_distance = haversine_distance(
            start_lat, start_lon, end_lat, end_lon
        )

        sample_coords = np.array(
            [[pt["latitude"], pt["longitude"]] for pt in interpolated]
        )
        data_coords = df[["latitude", "longitude"]].values

        # Pairwise distances: (samples, N_locations)
        dist_mat = distance_matrix(sample_coords, data_coords)

        segments = []
        scores = []

        for idx, pt in enumerate(interpolated):
            dists = dist_mat[idx]
            min_loc_idx = int(np.argmin(dists))
            min_dist = float(dists[min_loc_idx])
            nearest_row = df.iloc[min_loc_idx]

            # Points strictly within corridor_km
            in_corridor_mask = dists <= corridor_km
            if np.any(in_corridor_mask):
                corridor_subset = df[in_corridor_mask]
                corridor_score = float(corridor_subset["risk_score"].mean())
            else:
                corridor_score = float(nearest_row["risk_score"])

            score = round(corridor_score, 2)
            scores.append(score)
            exposure = classify_exposure(score)

            segments.append(
                {
                    "sequence": pt["sequence"],
                    "latitude": pt["latitude"],
                    "longitude": pt["longitude"],
                    "nearest_location_id": int(nearest_row["location_id"]),
                    "distance_to_risk_point_km": round(min_dist, 3),
                    "risk_score": score,
                    "risk_level": str(nearest_row["risk_level"]),
                    "exposure_level": exposure,
                }
            )

        avg_score = round(float(np.mean(scores)), 2) if scores else 0.0
        max_score = round(float(np.max(scores)), 2) if scores else 0.0
        high_segments = int(sum(1 for s in scores if s >= 60.0))
        vh_segments = int(sum(1 for s in scores if s >= 75.0))
        overall_exposure = classify_exposure(avg_score)

        return {
            "route": {
                "start": {
                    "latitude": round(start_lat, 6),
                    "longitude": round(start_lon, 6),
                },
                "end": {
                    "latitude": round(end_lat, 6),
                    "longitude": round(end_lon, 6),
                },
                "distance_km": total_distance,
            },
            "corridor_km": float(corridor_km),
            "exposure": {
                "average_risk_score": avg_score,
                "maximum_risk_score": max_score,
                "high_exposure_segments": high_segments,
                "very_high_exposure_segments": vh_segments,
                "overall_exposure": overall_exposure,
                "exposure_level": overall_exposure,
            },
            "segments": segments,
            "disclaimer": DISCLAIMER_TEXT,
        }

    # ==========================================
    # FEATURE 4: ROUTE RISK RANKING
    # ==========================================
    def get_ranked_corridors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Identifies and ranks potential high-risk corridors across the FLOWSIGHT grid.
        Constructs candidate corridors between proximate elevated-risk clusters.
        """
        if self._cached_corridors is not None:
            return self._cached_corridors[:limit]

        df = self.get_df()
        high_risk_df = df[df["risk_score"] >= 70.0].sort_values(
            "risk_score", ascending=False
        )

        candidates = []
        seen_pairs = set()

        coords = high_risk_df[["latitude", "longitude"]].values
        n_high = len(high_risk_df)

        if n_high >= 2:
            dist_mat = distance_matrix(coords, coords)

            for i in range(min(n_high, 40)):
                for j in range(i + 1, min(n_high, 40)):
                    d = float(dist_mat[i, j])
                    # Pick corridors between 0.8 km and 5.0 km
                    if 0.8 <= d <= 5.0:
                        row_i = high_risk_df.iloc[i]
                        row_j = high_risk_df.iloc[j]
                        pair_key = (
                            min(row_i["location_id"], row_j["location_id"]),
                            max(row_i["location_id"], row_j["location_id"]),
                        )
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        # Quick sample along corridor
                        route_analysis = self.analyze_route(
                            start_lat=float(row_i["latitude"]),
                            start_lon=float(row_i["longitude"]),
                            end_lat=float(row_j["latitude"]),
                            end_lon=float(row_j["longitude"]),
                            corridor_km=0.3,
                            samples=15,
                        )

                        exp = route_analysis["exposure"]
                        candidates.append(
                            {
                                "start": {
                                    "location_id": int(row_i["location_id"]),
                                    "latitude": float(row_i["latitude"]),
                                    "longitude": float(row_i["longitude"]),
                                },
                                "end": {
                                    "location_id": int(row_j["location_id"]),
                                    "latitude": float(row_j["latitude"]),
                                    "longitude": float(row_j["longitude"]),
                                },
                                "distance_km": route_analysis["route"]["distance_km"],
                                "average_risk_score": exp["average_risk_score"],
                                "maximum_risk_score": exp["maximum_risk_score"],
                                "high_risk_points": exp["high_exposure_segments"],
                                "very_high_risk_points": exp["very_high_exposure_segments"],
                                "exposure_level": exp["overall_exposure"],
                            }
                        )

        # Sort by composite exposure score: average_risk_score + weight on very high points
        candidates.sort(
            key=lambda c: (
                c["average_risk_score"] * 0.7 + c["maximum_risk_score"] * 0.3 + c["very_high_risk_points"] * 2.0
            ),
            reverse=True,
        )

        ranked = []
        for rank, c in enumerate(candidates, start=1):
            c_copy = dict(c)
            c_copy["corridor_id"] = f"corridor_{rank}"
            c_copy["name"] = f"Risk Corridor {rank}"
            ranked.append(c_copy)

        self._cached_corridors = ranked
        return self._cached_corridors[:limit]

    # ==========================================
    # FEATURE 5: IMPACT SUMMARY
    # ==========================================
    def get_summary(self) -> Dict[str, Any]:
        """
        Citywide spatial impact summary based strictly on the FLOWSIGHT dataset.
        """
        df = self.get_df()

        very_high_count = int((df["risk_score"] >= 75.0).sum())
        high_count = int(
            ((df["risk_score"] >= 60.0) & (df["risk_score"] < 75.0)).sum()
        )
        mod_count = int(
            ((df["risk_score"] >= 40.0) & (df["risk_score"] < 60.0)).sum()
        )
        low_count = int((df["risk_score"] < 40.0).sum())

        highest_row = df.sort_values("risk_score", ascending=False).iloc[0]

        top_corridors = self.get_ranked_corridors(limit=5)

        # Area estimation using grid cell resolution (~500m x ~500m = ~0.25 km²)
        est_high_area = round(float((very_high_count + high_count) * GRID_CELL_AREA_KM2), 2)
        est_very_high_area = round(float(very_high_count * GRID_CELL_AREA_KM2), 2)

        return {
            "total_locations": len(df),
            "very_high_locations": very_high_count,
            "high_locations": high_count,
            "moderate_locations": mod_count,
            "low_locations": low_count,
            "highest_risk_location": {
                "location_id": int(highest_row["location_id"]),
                "latitude": float(highest_row["latitude"]),
                "longitude": float(highest_row["longitude"]),
                "risk_score": float(highest_row["risk_score"]),
                "risk_level": str(highest_row["risk_level"]),
                "priority": int(highest_row["priority"]),
            },
            "highest_risk_score": float(highest_row["risk_score"]),
            "estimated_high_risk_area_km2": est_high_area,
            "estimated_very_high_risk_area_km2": est_very_high_area,
            "area_estimation_methodology": (
                f"Model estimate based on spatial grid cell resolution "
                f"(~{GRID_CELL_AREA_KM2} km² per location at ~500m spacing). "
                f"This is an analytical spatial model estimate, not a surveyed flood extent."
            ),
            "highest_exposure_corridors": top_corridors,
            "disclaimer": DISCLAIMER_TEXT,
        }

    # ==========================================
    # FEATURE 6: GEOJSON OUTPUT
    # ==========================================
    def get_geojson(
        self,
        include_points: bool = True,
        include_corridors: bool = True,
        include_influence_areas: bool = True,
        top_n_hotspots: int = 15,
        min_risk: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Generate a valid GeoJSON FeatureCollection containing FLOWSIGHT points,
        model-estimated influence polygons, and high-risk corridor LineStrings.
        """
        df = self.get_df()
        features: List[Dict[str, Any]] = []

        # 1. Point features
        if include_points:
            subset = df[df["risk_score"] >= min_risk]
            for _, row in subset.iterrows():
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [
                                float(row["longitude"]),
                                float(row["latitude"]),
                            ],
                        },
                        "properties": {
                            "feature_type": "risk_point",
                            "location_id": int(row["location_id"]),
                            "risk_score": float(row["risk_score"]),
                            "risk_level": str(row["risk_level"]),
                            "priority": int(row["priority"]),
                            "exposure_level": classify_exposure(
                                float(row["risk_score"])
                            ),
                            "elevation": float(row.get("elevation", 0.0)),
                            "slope": float(row.get("slope", 0.0)),
                            "built_up": float(row.get("built_up", 0.0)),
                            "rainfall": float(row.get("rainfall", 0.0)),
                            "road_density": float(row.get("road_density", 0.0)),
                        },
                    }
                )

        # 2. Influence circles / polygons for top hotspots
        if include_influence_areas:
            top_hotspots = df.sort_values("risk_score", ascending=False).head(
                top_n_hotspots
            )
            for _, row in top_hotspots.iterrows():
                bands = self.calculate_radius_bands(
                    float(row["latitude"]), float(row["longitude"])
                )
                rec_r, reason = self.derive_recommended_radius(
                    bands, float(row["risk_score"])
                )
                circle_coords = generate_circle_polygon(
                    float(row["latitude"]),
                    float(row["longitude"]),
                    radius_km=rec_r,
                    num_points=32,
                )

                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [circle_coords],
                        },
                        "properties": {
                            "feature_type": "risk_influence_area",
                            "origin_location_id": int(row["location_id"]),
                            "radius_km": rec_r,
                            "reason": reason,
                            "risk_score": float(row["risk_score"]),
                            "risk_level": str(row["risk_level"]),
                            "exposure_level": classify_exposure(
                                float(row["risk_score"])
                            ),
                        },
                    }
                )

        # 3. High-risk corridor LineStrings
        if include_corridors:
            corridors = self.get_ranked_corridors(limit=10)
            for c in corridors:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [c["start"]["longitude"], c["start"]["latitude"]],
                                [c["end"]["longitude"], c["end"]["latitude"]],
                            ],
                        },
                        "properties": {
                            "feature_type": "risk_corridor",
                            "corridor_id": c["corridor_id"],
                            "name": c["name"],
                            "distance_km": c["distance_km"],
                            "average_risk_score": c["average_risk_score"],
                            "maximum_risk_score": c["maximum_risk_score"],
                            "high_risk_points": c["high_risk_points"],
                            "very_high_risk_points": c["very_high_risk_points"],
                            "exposure_level": c["exposure_level"],
                        },
                    }
                )

        return {
            "type": "FeatureCollection",
            "metadata": {
                "total_features": len(features),
                "disclaimer": DISCLAIMER_TEXT,
            },
            "features": features,
        }

    # ==========================================
    # FEATURE 7: SINGLE LOCATION IMPACT
    # ==========================================
    def get_location_impact(self, location_id: int) -> Dict[str, Any]:
        """
        Combines spatial influence radius, nearby exposure points,
        nearby corridors, and inspection actions for one location.
        """
        loc = self.get_location_by_id(location_id)
        bands = self.calculate_radius_bands(loc["latitude"], loc["longitude"])
        rec_radius, rec_reason = self.derive_recommended_radius(
            bands, loc["risk_score"]
        )

        affected = self.get_affected_areas(
            location_id, radius_km=rec_radius, limit=20
        )

        # Find corridors starting or ending near this location (within 2 km)
        all_corridors = self.get_ranked_corridors(limit=15)
        nearby_corridors = []
        for c in all_corridors:
            d_start = haversine_distance(
                loc["latitude"],
                loc["longitude"],
                c["start"]["latitude"],
                c["start"]["longitude"],
            )
            d_end = haversine_distance(
                loc["latitude"],
                loc["longitude"],
                c["end"]["latitude"],
                c["end"]["longitude"],
            )
            if d_start <= 2.0 or d_end <= 2.0:
                c_data = dict(c)
                c_data["distance_to_origin_km"] = min(d_start, d_end)
                nearby_corridors.append(c_data)

        # Formulate actionable inspection recommendation based on model data
        basis = [
            f"Risk score is {loc['risk_score']:.2f} ({loc['risk_level']} Risk Level)",
            f"Elevation: {loc['elevation']:.1f} m, Slope: {loc['slope']:.2f}°",
            f"Built-up intensity: {loc['built_up']:.2f}, Road density: {loc['road_density']:.2f}",
            f"Estimated exposure influence extends {rec_radius:.1f} km with {affected['count']} proximate points.",
        ]

        if loc["priority"] == 1:
            rec_action = (
                "Priority 1 Field Inspection: Prioritize culvert, stormwater drain capacity, "
                "and low-lying runoff channels across the identified exposure area."
            )
        elif loc["priority"] == 2:
            rec_action = (
                "Priority 2 Field Inspection: Monitor localized drainage convergence "
                "and road-edge runoff during intense rainfall events."
            )
        else:
            rec_action = (
                "Routine Monitoring: Periodically inspect local catchment and road surface conditions."
            )

        return {
            "location": {
                "location_id": loc["location_id"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "risk_score": loc["risk_score"],
                "risk_level": loc["risk_level"],
                "priority": loc["priority"],
            },
            "impact_radius": {
                "recommended_radius_km": rec_radius,
                "reason": rec_reason,
                "bands": bands,
            },
            "nearby_exposure": {
                "count": affected["count"],
                "radius_km": rec_radius,
                "locations": affected["locations"],
            },
            "route_exposure": {
                "nearby_corridors": nearby_corridors,
            },
            "action": {
                "recommended": rec_action,
                "basis": basis,
            },
            "disclaimer": DISCLAIMER_TEXT,
        }


# Global engine instance
impact_engine = ImpactEngine()
