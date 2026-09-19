from pathlib import Path
import pandas as pd
import numpy as np


# Approximate Hyderabad study area.
# We will refine this boundary when the actual city boundary
# dataset is incorporated.
LAT_MIN = 17.20
LAT_MAX = 17.60
LON_MIN = 78.20
LON_MAX = 78.70

# Approximate spacing.
# ~0.005 degrees is roughly 500 m in latitude.
GRID_STEP = 0.005


def generate_hyderabad_grid() -> pd.DataFrame:
    """
    Generate a regular geographic grid covering the
    initial Hyderabad study area.
    """

    latitudes = np.arange(LAT_MIN, LAT_MAX, GRID_STEP)
    longitudes = np.arange(LON_MIN, LON_MAX, GRID_STEP)

    records = []

    location_id = 1

    for lat in latitudes:
        for lon in longitudes:
            records.append(
                {
                    "location_id": location_id,
                    "latitude": round(float(lat), 6),
                    "longitude": round(float(lon), 6),
                }
            )

            location_id += 1

    return pd.DataFrame(records)


def save_grid(output_path: str | Path) -> pd.DataFrame:
    """
    Generate and save the Hyderabad grid as CSV.
    """

    output_path = Path(output_path)

    df = generate_hyderabad_grid()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False)

    return df


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "data" / "locations.csv"

    df = save_grid(output)

    print(f"Generated {len(df):,} grid locations.")
    print(f"Saved to: {output}")