from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

INPUT_FILE = DATA_DIR / "locations_terrain.csv"
OUTPUT_FILE = DATA_DIR / "locations_terrain.csv"


def calculate_slope(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate approximate terrain slope from neighboring
    elevation points.

    Slope is expressed in degrees.
    """

    df = df.copy()

    # ---------------------------------------------------------
    # Create a geographic elevation grid
    # ---------------------------------------------------------

    elevation_grid = df.pivot(
        index="latitude",
        columns="longitude",
        values="elevation",
    )

    elevation_grid = elevation_grid.sort_index()
    elevation_grid = elevation_grid.sort_index(axis=1)

    elevations = elevation_grid.to_numpy(
        dtype=float
    )

    latitudes = elevation_grid.index.to_numpy(
        dtype=float
    )

    longitudes = elevation_grid.columns.to_numpy(
        dtype=float
    )

    # ---------------------------------------------------------
    # Fill missing elevation values using nearest available
    # value in the grid.
    # ---------------------------------------------------------

    elevation_grid = elevation_grid.interpolate(
        axis=0,
        limit_direction="both",
    )

    elevation_grid = elevation_grid.interpolate(
        axis=1,
        limit_direction="both",
    )

    elevations = elevation_grid.to_numpy(
        dtype=float
    )

    # ---------------------------------------------------------
    # Geographic spacing
    # ---------------------------------------------------------

    mean_latitude = np.mean(latitudes)

    meters_per_degree_lat = 111_320.0

    meters_per_degree_lon = (
        111_320.0
        * np.cos(
            np.radians(mean_latitude)
        )
    )

    # Grid spacing in degrees.

    if len(latitudes) > 1:
        lat_spacing = np.mean(
            np.diff(latitudes)
        )
    else:
        lat_spacing = 0.04

    if len(longitudes) > 1:
        lon_spacing = np.mean(
            np.diff(longitudes)
        )
    else:
        lon_spacing = 0.04

    dy = (
        abs(lat_spacing)
        * meters_per_degree_lat
    )

    dx = (
        abs(lon_spacing)
        * meters_per_degree_lon
    )

    # ---------------------------------------------------------
    # Calculate elevation gradients.
    # ---------------------------------------------------------

    dz_dy, dz_dx = np.gradient(
        elevations,
        dy,
        dx,
    )

    # ---------------------------------------------------------
    # Calculate slope.
    #
    # slope = atan(sqrt(
    #     dz/dx² + dz/dy²
    # ))
    # ---------------------------------------------------------

    slope_radians = np.arctan(
        np.sqrt(
            dz_dx ** 2
            + dz_dy ** 2
        )
    )

    slope_degrees = np.degrees(
        slope_radians
    )

    slope_degrees = np.clip(
        slope_degrees,
        0,
        90,
    )

    # ---------------------------------------------------------
    # Convert grid back into a dataframe.
    # ---------------------------------------------------------

    slope_grid = pd.DataFrame(
        slope_degrees,
        index=elevation_grid.index,
        columns=elevation_grid.columns,
    )

    slope_grid.index.name = "latitude"
    slope_grid.columns.name = "longitude"

    slope_points = (
        slope_grid
        .stack()
        .reset_index()
    )

    slope_points.columns = [
        "latitude",
        "longitude",
        "slope",
    ]

    # ---------------------------------------------------------
    # Join slope back to original dataset.
    # ---------------------------------------------------------

    df = df.drop(
        columns=["slope"],
        errors="ignore",
    )

    df = df.merge(
        slope_points,
        on=[
            "latitude",
            "longitude",
        ],
        how="left",
    )

    df["slope"] = (
        df["slope"]
        .astype(float)
        .round(3)
    )

    return df


def main():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Missing file:\n{INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    print(
        f"Loaded {len(df):,} locations."
    )

    if "elevation" not in df.columns:

        raise ValueError(
            "Elevation column is missing."
        )

    print(
        "Calculating slope from "
        "neighboring elevation values..."
    )

    df = calculate_slope(df)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=" * 60)
    print("SLOPE CALCULATION COMPLETE")
    print("=" * 60)

    print()
    print("Slope statistics:")

    print(
        df["slope"].describe()
    )

    print()
    print("Sample:")

    print(
        df[
            [
                "location_id",
                "latitude",
                "longitude",
                "elevation",
                "slope",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()