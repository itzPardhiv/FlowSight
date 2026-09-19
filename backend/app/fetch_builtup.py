from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.mask import mask
from shapely.geometry import box, mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

INPUT_FILE = DATA_DIR / "locations_terrain.csv"
OUTPUT_FILE = DATA_DIR / "locations_features.csv"

# ------------------------------------------------------------
# GHSL GHS-BUILT-S R2023A
# ------------------------------------------------------------
#
# We will use the WGS84 1 km product for the MVP.
#
# IMPORTANT:
# The exact downloadable tile URL can change with GHSL releases.
# This script expects the downloaded GeoTIFF/ZIP to be placed
# in backend/data/ghsl/.
# ------------------------------------------------------------

GHSL_DIR = DATA_DIR / "ghsl"


def find_raster():
    """
    Find a downloaded GHSL GeoTIFF inside backend/data/ghsl.
    """

    tif_files = list(GHSL_DIR.rglob("*.tif")) + list(
        GHSL_DIR.rglob("*.tiff")
    )

    if not tif_files:
        return None

    return tif_files[0]


def calculate_built_up_fraction(
    raster_path,
    latitude,
    longitude,
):
    """
    Read the GHSL built-up surface value around one location.

    GHSL reports built-up surface in square metres.

    For the 1 km product, the value is converted into an
    approximate percentage of the grid-cell area.
    """

    with rasterio.open(raster_path) as src:

        point_x = longitude
        point_y = latitude

        row, col = src.index(
            point_x,
            point_y,
        )

        value = src.read(
            1,
            window=rasterio.windows.Window(
                col,
                row,
                1,
                1,
            ),
        )[0, 0]

        if value == src.nodata:
            return np.nan

        value = float(value)

        # Approximate area of a 1 km cell.
        cell_area = 1_000_000.0

        fraction = (
            value / cell_area
        ) * 100.0

        return float(
            np.clip(
                fraction,
                0,
                100,
            )
        )


def main():

    # --------------------------------------------------------
    # Check input
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing input file:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    print(
        f"Loaded {len(df):,} FLOWSIGHT locations."
    )

    # --------------------------------------------------------
    # Locate GHSL raster
    # --------------------------------------------------------

    GHSL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    raster_path = find_raster()

    if raster_path is None:

        print()
        print("=" * 60)
        print("GHSL DATASET REQUIRED")
        print("=" * 60)
        print()
        print(
            "No GHSL GeoTIFF was found."
        )
        print()
        print(
            "Download the GHS-BUILT-S R2023A "
            "WGS84 1 km raster from the official "
            "GHSL download wizard."
        )
        print()
        print(
            "Place the extracted .tif file here:"
        )
        print(
            GHSL_DIR
        )
        print()
        print(
            "Then run this script again."
        )

        return

    print(
        f"Using GHSL raster:\n{raster_path}"
    )

    # --------------------------------------------------------
    # Extract built-up fraction
    # --------------------------------------------------------

    print()
    print(
        "Extracting built-up values..."
    )

    built_up_values = []

    for index, row in df.iterrows():

        value = calculate_built_up_fraction(
            raster_path,
            float(row["latitude"]),
            float(row["longitude"]),
        )

        built_up_values.append(
            value
        )

        if (
            (index + 1) % 100 == 0
            or index == len(df) - 1
        ):
            print(
                f"Processed "
                f"{index + 1:,}/"
                f"{len(df):,}"
            )

    # --------------------------------------------------------
    # Add feature
    # --------------------------------------------------------

    df["built_up"] = built_up_values

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    valid = df["built_up"].notna().sum()

    print()
    print(
        f"Valid built-up values: "
        f"{valid:,}/{len(df):,}"
    )

    if valid == 0:

        raise RuntimeError(
            "No valid GHSL built-up values "
            "were extracted."
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=" * 60)
    print("BUILT-UP EXTRACTION COMPLETE")
    print("=" * 60)

    print()
    print(
        f"Output: {OUTPUT_FILE}"
    )

    print()
    print(
        "Built-up statistics:"
    )

    print(
        df["built_up"].describe()
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
                "built_up",
            ]
        ]
        .head(10)
        .to_string(
            index=False
        )
    )

    print()
    print("SUCCESS")


if __name__ == "__main__":
    main()