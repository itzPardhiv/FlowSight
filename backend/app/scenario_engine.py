from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from .geo_utils import distance_matrix
from .impact_engine import impact_engine, DISCLAIMER_TEXT

SCENARIO_DISCLAIMER = (
    "Model Scenario / Event Replay: All rainfall modifications and replay events "
    "are analytical model simulations derived from FLOWSIGHT's baseline risk index. "
    "They do not represent observed historical flood sensors, real-time telemetry, "
    "or guaranteed inundation extent."
)

SCENARIOS_CATALOG: Dict[str, Dict[str, Any]] = {
    "heavy_downpour_120": {
        "scenario_id": "heavy_downpour_120",
        "name": "Intense Cloudburst Scenario (+20%)",
        "type": "Model Scenario",
        "rainfall_multiplier": 1.20,
        "description": (
            "Simulates a +20% uniform rainfall intensity surge across all Hyderabad catchments "
            "to stress-test surface runoff response and identify rapidly saturating locations."
        ),
    },
    "extreme_monsoon_150": {
        "scenario_id": "extreme_monsoon_150",
        "name": "Severe Monsoon Storm Scenario (+50%)",
        "type": "Model Scenario",
        "rainfall_multiplier": 1.50,
        "description": (
            "Models an acute +50% monsoon depression event, identifying catchments that "
            "transition from moderate exposure into critical high and very high risk thresholds."
        ),
    },
    "historical_replay_2020_model": {
        "scenario_id": "historical_replay_2020_model",
        "name": "October 2020 Synoptic Rain Pattern — Model Replay",
        "type": "Event Replay",
        "rainfall_multiplier": 1.80,
        "description": (
            "Simulates the spatial rainfall distribution modeled after the October 2020 synoptic "
            "depression (~1.80x peak rainfall with heightened eastern and central basin concentration). "
            "Strictly an analytical model replay; does not represent observed flood sensor readings."
        ),
    },
    "localized_flash_storm": {
        "scenario_id": "localized_flash_storm",
        "name": "Central Basin Flash Storm (+40% localized)",
        "type": "Model Scenario",
        "rainfall_multiplier": 1.40,
        "description": (
            "Models a localized high-intensity convective cell concentrated over low-elevation "
            "central drainage basins and Musi catchment zones."
        ),
    },
}


def normalize_series(s: pd.Series, min_val: float, max_val: float) -> pd.Series:
    if max_val == min_val:
        return pd.Series(0.0, index=s.index)
    return (s - min_val) / (max_val - min_val)


def classify_risk_level(score: float) -> str:
    if score < 25.0:
        return "Low"
    elif score < 50.0:
        return "Moderate"
    elif score < 75.0:
        return "High"
    else:
        return "Very High"


class ScenarioEngine:
    """
    Historical Comparison & Event Replay Engine for FLOWSIGHT.
    Computes deterministic scenario-adjusted risk scores and comparisons
    against the baseline 1,013-location dataset.
    """

    def __init__(self):
        self._cached_scenario_results: Dict[str, pd.DataFrame] = {}

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Returns all registered scenarios with baseline comparison previews."""
        scenarios = []
        for s_id in SCENARIOS_CATALOG:
            details = self.get_scenario_details(s_id)
            scenarios.append(
                {
                    "scenario_id": details["scenario_id"],
                    "name": details["name"],
                    "type": details["type"],
                    "description": details["description"],
                    "rainfall_multiplier": details["rainfall_multiplier"],
                    "affected_location_count": details["affected_location_count"],
                    "average_risk": details["average_risk"],
                    "maximum_risk": details["maximum_risk"],
                    "risk_distribution": details["risk_distribution"],
                    "disclaimer": SCENARIO_DISCLAIMER,
                }
            )
        return scenarios

    def evaluate_scenario(self, scenario_id: str) -> pd.DataFrame:
        """
        Evaluates a scenario on all 1,013 locations.
        Preserves baseline feature definitions while recalculating scenario rainfall risk.
        """
        if scenario_id in self._cached_scenario_results:
            return self._cached_scenario_results[scenario_id]

        if scenario_id not in SCENARIOS_CATALOG:
            raise KeyError(f"Scenario '{scenario_id}' not found in catalog")

        cfg = SCENARIOS_CATALOG[scenario_id]
        df = impact_engine.get_df().copy()

        # Calibration bounds from baseline features
        elev_min, elev_max = df["elevation"].min(), df["elevation"].max()
        slope_min, slope_max = df["slope"].min(), df["slope"].max()
        built_min, built_max = df["built_up"].min(), df["built_up"].max()
        rf_min, rf_max = df["rainfall"].min(), df["rainfall"].max()
        road_min, road_max = df["road_density"].min(), df["road_density"].max()

        elev_risk = 1.0 - normalize_series(df["elevation"], elev_min, elev_max)
        slope_risk = 1.0 - normalize_series(df["slope"], slope_min, slope_max)
        builtup_risk = normalize_series(df["built_up"], built_min, built_max)
        road_risk = normalize_series(df["road_density"], road_min, road_max)

        base_rf_risk = normalize_series(df["rainfall"], rf_min, rf_max)

        # Scenario rainfall simulation & proportional risk scaling
        mult = cfg["rainfall_multiplier"]
        if scenario_id == "historical_replay_2020_model":
            # October 2020 model: eastern and central spatial bias
            spatial_gradient = 1.0 + 0.15 * np.sin((df["longitude"] - 78.35) * 10)
            scenario_rf_risk = np.clip(base_rf_risk * mult * spatial_gradient, 0.0, 2.0)
        elif scenario_id == "localized_flash_storm":
            # Central basin focus: low elevation points get higher intensity boost
            basin_factor = 1.0 + 0.20 * (1.0 - normalize_series(df["elevation"], elev_min, elev_max))
            scenario_rf_risk = np.clip(base_rf_risk * mult * basin_factor, 0.0, 2.0)
        else:
            scenario_rf_risk = np.clip(base_rf_risk * mult, 0.0, 2.0)

        # Baseline risk formula: 0.25 elev + 0.20 slope + 0.25 builtup + 0.20 rainfall + 0.10 road
        scenario_scores = (
            0.25 * elev_risk
            + 0.20 * slope_risk
            + 0.25 * builtup_risk
            + 0.20 * scenario_rf_risk
            + 0.10 * road_risk
        ) * 100.0

        scenario_scores = np.clip(scenario_scores, 0.0, 100.0).round(2)

        df["scenario_risk_score"] = scenario_scores
        df["scenario_risk_level"] = df["scenario_risk_score"].apply(classify_risk_level)
        df["risk_delta"] = (df["scenario_risk_score"] - df["risk_score"]).round(2)

        self._cached_scenario_results[scenario_id] = df
        return df

    def get_scenario_details(self, scenario_id: str) -> Dict[str, Any]:
        """Returns scenario configuration, impact statistics, and top affected locations."""
        if scenario_id not in SCENARIOS_CATALOG:
            raise KeyError(f"Scenario '{scenario_id}' not found")

        cfg = SCENARIOS_CATALOG[scenario_id]
        df = self.evaluate_scenario(scenario_id)

        avg_risk = round(float(df["scenario_risk_score"].mean()), 2)
        max_risk = round(float(df["scenario_risk_score"].max()), 2)

        # Count affected: locations with High or Very High risk under this scenario
        affected_count = int((df["scenario_risk_score"] >= 60.0).sum())

        counts = df["scenario_risk_level"].value_counts().to_dict()
        risk_dist = {
            "Very High": int(counts.get("Very High", 0)),
            "High": int(counts.get("High", 0)),
            "Moderate": int(counts.get("Moderate", 0)),
            "Low": int(counts.get("Low", 0)),
        }

        # Locality mapping
        localities_file = Path(__file__).resolve().parent / "localities.json"
        locality_map: Dict[str, str] = {}
        if localities_file.exists():
            import json
            with open(localities_file, "r", encoding="utf-8") as f:
                locality_map = json.load(f)

        top_df = df.sort_values("scenario_risk_score", ascending=False).head(10)
        top_locations = []
        for _, row in top_df.iterrows():
            loc_id = int(row["location_id"])
            top_locations.append(
                {
                    "location_id": loc_id,
                    "locality": locality_map.get(str(loc_id), f"Location {loc_id}"),
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "baseline_risk_score": float(row["risk_score"]),
                    "scenario_risk_score": float(row["scenario_risk_score"]),
                    "risk_delta": float(row["risk_delta"]),
                    "baseline_risk_level": str(row["risk_level"]),
                    "scenario_risk_level": str(row["scenario_risk_level"]),
                    "priority": int(row["priority"]),
                }
            )

        return {
            "scenario_id": cfg["scenario_id"],
            "name": cfg["name"],
            "type": cfg["type"],
            "description": cfg["description"],
            "rainfall_multiplier": float(cfg["rainfall_multiplier"]),
            "affected_location_count": affected_count,
            "average_risk": avg_risk,
            "maximum_risk": max_risk,
            "risk_distribution": risk_dist,
            "top_affected_locations": top_locations,
            "disclaimer": SCENARIO_DISCLAIMER,
        }

    def compare_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """Compares the selected scenario against the baseline model."""
        if scenario_id not in SCENARIOS_CATALOG:
            raise KeyError(f"Scenario '{scenario_id}' not found")

        cfg = SCENARIOS_CATALOG[scenario_id]
        df = self.evaluate_scenario(scenario_id)

        base_avg = round(float(df["risk_score"].mean()), 2)
        scen_avg = round(float(df["scenario_risk_score"].mean()), 2)
        base_max = round(float(df["risk_score"].max()), 2)
        scen_max = round(float(df["scenario_risk_score"].max()), 2)

        # Locations whose risk level increased
        level_ranks = {"Low": 1, "Moderate": 2, "High": 3, "Very High": 4}
        base_rank = df["risk_level"].map(level_ranks)
        scen_rank = df["scenario_risk_level"].map(level_ranks)

        increased_mask = scen_rank > base_rank
        decreased_mask = scen_rank < base_rank
        num_increased = int(increased_mask.sum())
        num_decreased = int(decreased_mask.sum())

        # Baseline vs scenario distributions
        base_counts = df["risk_level"].value_counts().to_dict()
        scen_counts = df["scenario_risk_level"].value_counts().to_dict()

        base_dist = {
            "Very High": int(base_counts.get("Very High", 0)),
            "High": int(base_counts.get("High", 0)),
            "Moderate": int(base_counts.get("Moderate", 0)),
            "Low": int(base_counts.get("Low", 0)),
        }
        scen_dist = {
            "Very High": int(scen_counts.get("Very High", 0)),
            "High": int(scen_counts.get("High", 0)),
            "Moderate": int(scen_counts.get("Moderate", 0)),
            "Low": int(scen_counts.get("Low", 0)),
        }

        # Newly elevated hotspots: was Low or Moderate in baseline, became High or Very High in scenario
        newly_elevated_mask = (df["risk_score"] < 60.0) & (df["scenario_risk_score"] >= 60.0)
        elevated_df = df[newly_elevated_mask].sort_values("scenario_risk_score", ascending=False)

        # Locality mapping
        localities_file = Path(__file__).resolve().parent / "localities.json"
        locality_map: Dict[str, str] = {}
        if localities_file.exists():
            import json
            with open(localities_file, "r", encoding="utf-8") as f:
                locality_map = json.load(f)

        newly_elevated_list = []
        for _, row in elevated_df.head(15).iterrows():
            loc_id = int(row["location_id"])
            newly_elevated_list.append(
                {
                    "location_id": loc_id,
                    "locality": locality_map.get(str(loc_id), f"Location {loc_id}"),
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "baseline_risk_score": float(row["risk_score"]),
                    "scenario_risk_score": float(row["scenario_risk_score"]),
                    "risk_delta": float(row["risk_delta"]),
                    "baseline_risk_level": str(row["risk_level"]),
                    "scenario_risk_level": str(row["scenario_risk_level"]),
                }
            )

        # Top changed locations by absolute risk score delta
        top_changed_df = df.sort_values("risk_delta", ascending=False).head(15)
        top_changed_list = []
        for _, row in top_changed_df.iterrows():
            loc_id = int(row["location_id"])
            top_changed_list.append(
                {
                    "location_id": loc_id,
                    "locality": locality_map.get(str(loc_id), f"Location {loc_id}"),
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "baseline_risk_score": float(row["risk_score"]),
                    "scenario_risk_score": float(row["scenario_risk_score"]),
                    "risk_delta": float(row["risk_delta"]),
                    "baseline_risk_level": str(row["risk_level"]),
                    "scenario_risk_level": str(row["scenario_risk_level"]),
                }
            )

        return {
            "scenario_id": cfg["scenario_id"],
            "name": cfg["name"],
            "type": cfg["type"],
            "baseline_average_risk": base_avg,
            "scenario_average_risk": scen_avg,
            "baseline_maximum_risk": base_max,
            "scenario_maximum_risk": scen_max,
            "average_risk_delta": round(scen_avg - base_avg, 2),
            "maximum_risk_delta": round(scen_max - base_max, 2),
            "locations_whose_risk_level_increased": num_increased,
            "locations_whose_risk_level_decreased": num_decreased,
            "baseline_risk_distribution": base_dist,
            "scenario_risk_distribution": scen_dist,
            "newly_elevated_hotspots_count": len(elevated_df),
            "newly_elevated_hotspots": newly_elevated_list,
            "top_changed_locations": top_changed_list,
            "disclaimer": SCENARIO_DISCLAIMER,
        }


# Global singleton
scenario_engine = ScenarioEngine()
