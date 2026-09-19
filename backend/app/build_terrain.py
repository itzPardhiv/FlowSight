from pathlib import Path
import time

import pandas as pd
import requests


# ============================================================
# FLOWSIGHT — TERRAIN DATA BUILDER
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

INPUT_FILE = DATA_DIR / "locations.csv"
OUTPUT_FILE = DATA_DIR / "locations_terrain.csv"

API_URL = "https://api.open-meteo.com/v1/elevation"

# Smaller batches reduce the chance of rate limiting.
BATCH_SIZE = 50

# Delay between successful requests.
REQUEST_DELAY = 2

# Maximum number of retries after a 429/server error.
MAX_RETRIES = 5


def fetch_elevations(batch: pd.DataFrame) -> list[float]:
    """
    Fetch elevation values for one batch of coordinates.

    Uses Open-Meteo's elevation API with retry/backoff handling.
    """

    latitudes = ",".join(
        str(round(float(value), 6))
        for value in batch["latitude"]
    )

    longitudes = ",".join(
        str(round(float(value), 6))
        for value in batch["longitude"]
    )

    params = {
        "latitude": latitudes,
        "longitude": longitudes,
    }

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.get(
                API_URL,
                params=params,
                timeout=60,
            )

            # ------------------------------------------------
            # Rate limit
            # ------------------------------------------------

            if response.status_code == 429:

                wait_time = 10 * attempt

                print(
                    f"Rate limited (429). "
                    f"Waiting {wait_time}s..."
                )

                time.sleep(wait_time)

                continue

            # ------------------------------------------------
            # Server errors
            # ------------------------------------------------

            if response.status_code >= 500:

                wait_time = 5 * attempt

                print(
                    f"Server error {response.status_code}. "
                    f"Retrying in {wait_time}s..."
                )

                time.sleep(wait_time)

                continue

            response.raise_for_status()

            data = response.json()

            elevations = data.get("elevation")

            if elevations is None:

                raise RuntimeError(
                    "API response did not contain "
                    "'elevation'."
                )

            if len(elevations) != len(batch):

                raise RuntimeError(
                    "Number of elevations returned "
                    "does not match number of locations."
                )

            return [
                float(value)
                for value in elevations
            ]

        except requests.RequestException as error:

            if attempt == MAX_RETRIES:
                raise

            wait_time = 5 * attempt

            print(
                f"Request error: {error}"
            )

            print(
                f"Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

    raise RuntimeError(
        "Elevation API failed after all retries."
    )


def create_smaller_grid():
    """
    Reduce the original 8,100-point grid to approximately
    1,000 locations.

    This is sufficient for the competition MVP and keeps
    the frontend/API lightweight.
    """

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    print(
        f"Original grid: {len(df):,} locations"
    )

    # Take every 8th point.
    reduced = df.iloc[::8].copy()

    reduced = reduced.reset_index(drop=True)

    reduced.to_csv(
        INPUT_FILE,
        index=False,
    )

    print(
        f"Reduced grid: {len(reduced):,} locations"
    )

    return reduced


def main():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Check input
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Could not find:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    # --------------------------------------------------------
    # Reduce the grid if it is still very large.
    # --------------------------------------------------------

    if len(df) > 1500:

        df = create_smaller_grid()

    print()
    print("=" * 60)
    print("FLOWSIGHT TERRAIN BUILDER")
    print("=" * 60)
    print()

    print(
        f"Locations to process: {len(df):,}"
    )

    print(
        f"Batch size: {BATCH_SIZE}"
    )

    print()

    # --------------------------------------------------------
    # Process elevation
    # --------------------------------------------------------

    elevations = []

    total = len(df)

    for start in range(
        0,
        total,
        BATCH_SIZE,
    ):

        end = min(
            start + BATCH_SIZE,
            total,
        )

        batch = df.iloc[start:end]

        print(
            f"Processing "
            f"{start + 1}-{end} "
            f"of {total}"
        )

        batch_elevations = fetch_elevations(
            batch
        )

        elevations.extend(
            batch_elevations
        )

        # ----------------------------------------------------
        # Save an intermediate checkpoint.
        # ----------------------------------------------------

        checkpoint = df.iloc[
            :len(elevations)
        ].copy()

        checkpoint["elevation"] = elevations

        checkpoint.to_csv(
            OUTPUT_FILE,
            index=False,
        )

        print(
            f"Checkpoint saved "
            f"({len(elevations)}/{total})"
        )

        print()

        # ----------------------------------------------------
        # Be polite to the public API.
        # ----------------------------------------------------

        if end < total:
            time.sleep(REQUEST_DELAY)

    # --------------------------------------------------------
    # Final dataset
    # --------------------------------------------------------

    df["elevation"] = elevations

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=" * 60)
    print("TERRAIN DATA COMPLETE")
    print("=" * 60)
    print()

    print(
        f"Output: {OUTPUT_FILE}"
    )

    print(
        f"Rows: {len(df):,}"
    )

    print()

    print("Elevation statistics:")

    print(
        df["elevation"].describe()
    )

    print()

    print("Sample:")

    print(
        df.head(10).to_string(
            index=False
        )
    )

    print()
    print("SUCCESS")


if __name__ == "__main__":
    main()