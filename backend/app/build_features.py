from pathlib import Path
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

INPUT_FILE = DATA_DIR / "locations_terrain.csv"
OUTPUT_FILE = DATA_DIR / "locations_features.csv"


def normalize(series):
    minimum = series.min()
    maximum = series.max()

    if maximum == minimum:
        return pd.Series(
            np.zeros(len(series)),
            index=series.index,
        )

    return (
        (series - minimum)
        / (maximum - minimum)
    )


def main():

    print("=" * 60)
    print("FLOWSIGHT — FEATURE ENGINEERING")
    print("=" * 60)

    df = pd.read_csv(INPUT_FILE)

    print(
        f"Loaded {len(df):,} locations."
    )

    # --------------------------------------------------------
    # Existing real terrain features
    # --------------------------------------------------------

    df["elevation"] = pd.to_numeric(
        df["elevation"],
        errors="coerce",
    )

    df["slope"] = pd.to_numeric(
        df["slope"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # BUILT-UP
    #
    # Derived from spatial position + terrain for MVP.
    # Higher density around the Hyderabad urban core.
    # --------------------------------------------------------

    lat = df["latitude"]
    lon = df["longitude"]

    urban_center_lat = 17.385
    urban_center_lon = 78.4867

    distance = np.sqrt(
        ((lat - urban_center_lat) / 0.20) ** 2
        +
        ((lon - urban_center_lon) / 0.25) ** 2
    )

    urban_intensity = np.exp(
        -(distance ** 2)
    )

    # Built-up percentage estimate
    df["built_up"] = (
        15
        + 75 * urban_intensity
    )

    df["built_up"] = np.clip(
        df["built_up"],
        5,
        95,
    )

    # --------------------------------------------------------
    # RAINFALL
    #
    # Hyderabad monsoon design scenario.
    # Spatial variation is applied across the city.
    # --------------------------------------------------------

    rainfall_gradient = (
        1
        + 0.12
        * np.sin(
            (lon - 78.2) * 8
        )
    )

    df["rainfall"] = (
        85
        * rainfall_gradient
    )

    # --------------------------------------------------------
    # ROAD DENSITY
    #
    # Estimated urban road-density indicator.
    # Higher in developed/central areas.
    # --------------------------------------------------------

    df["road_density"] = (
        0.25
        + 0.75 * urban_intensity
    )

    df["road_density"] = np.clip(
        df["road_density"],
        0,
        1,
    )

    # --------------------------------------------------------
    # NORMALIZED FEATURES
    # --------------------------------------------------------

    elevation_risk = 1 - normalize(
        df["elevation"]
    )

    slope_risk = 1 - normalize(
        df["slope"]
    )

    builtup_risk = normalize(
        df["built_up"]
    )

    rainfall_risk = normalize(
        df["rainfall"]
    )

    road_risk = normalize(
        df["road_density"]
    )

    # --------------------------------------------------------
    # RISK SCORE
    # --------------------------------------------------------

    df["risk_score"] = (
        0.25 * elevation_risk
        + 0.20 * slope_risk
        + 0.25 * builtup_risk
        + 0.20 * rainfall_risk
        + 0.10 * road_risk
    ) * 100

    df["risk_score"] = df[
        "risk_score"
    ].round(2)

    # --------------------------------------------------------
    # RISK LEVEL
    # --------------------------------------------------------

    def risk_level(score):

        if score < 25:
            return "Low"

        if score < 50:
            return "Moderate"

        if score < 75:
            return "High"

        return "Very High"

    df["risk_level"] = (
        df["risk_score"]
        .apply(risk_level)
    )

    # --------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------

    df = df.sort_values(
        "risk_score",
        ascending=False,
    ).reset_index(
        drop=True
    )

    df["priority"] = (
        df.index + 1
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("FLOWSIGHT FEATURE ENGINEERING COMPLETE")
    print("=" * 60)

    print()
    print(
        f"Output: {OUTPUT_FILE}"
    )

    print()
    print("Columns:")

    print(
        df.columns.tolist()
    )

    print()
    print("Risk distribution:")

    print(
        df["risk_level"]
        .value_counts()
    )

    print()
    print("Top 10 priority locations:")

    print(
        df[
            [
                "location_id",
                "latitude",
                "longitude",
                "risk_score",
                "risk_level",
                "priority",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    print()
    print("SUCCESS")


if __name__ == "__main__":
    main()