from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "locations_features.csv"


app = FastAPI(
    title="FLOWSIGHT API",
    description="AI-assisted urban waterlogging risk analysis for Hyderabad.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}"
        )

    return pd.read_csv(DATA_FILE)


@app.get("/")
def root():
    return {
        "project": "FLOWSIGHT",
        "status": "online",
        "message": "See the flood before the street does.",
    }


@app.get("/api/stats")
def stats():
    df = load_data()

    return {
        "total_locations": len(df),
        "risk_distribution": (
            df["risk_level"]
            .value_counts()
            .to_dict()
        ),
        "average_risk_score": round(
            float(df["risk_score"].mean()),
            2,
        ),
        "highest_risk_score": round(
            float(df["risk_score"].max()),
            2,
        ),
    }


@app.get("/api/locations")
def locations():
    df = load_data()

    records = df[
        [
            "location_id",
            "latitude",
            "longitude",
            "risk_score",
            "risk_level",
            "priority",
            "elevation",
            "slope",
            "built_up",
            "rainfall",
            "road_density",
        ]
    ].to_dict(orient="records")

    return {
        "count": len(records),
        "locations": records,
    }


@app.get("/api/top-risk")
def top_risk(limit: int = 10):
    df = load_data()

    limit = max(1, min(limit, 100))

    result = (
        df.sort_values(
            "risk_score",
            ascending=False,
        )
        .head(limit)
    )

    return {
        "count": len(result),
        "locations": result[
            [
                "location_id",
                "latitude",
                "longitude",
                "risk_score",
                "risk_level",
                "priority",
            ]
        ].to_dict(orient="records"),
    }


@app.get("/api/locations/{location_id}/explanation")
def location_explanation(location_id: int):
    df = load_data()

    result = df[
        df["location_id"] == location_id
    ]

    if result.empty:
        raise HTTPException(
            status_code=404,
            detail="Location not found",
        )

    row = result.iloc[0]

    def normalized_risk(
        value,
        minimum,
        maximum,
    ):
        if maximum == minimum:
            return 0.0

        return float(
            (value - minimum)
            / (maximum - minimum)
        )

    elevation_risk = 1 - normalized_risk(
        row["elevation"],
        df["elevation"].min(),
        df["elevation"].max(),
    )

    slope_risk = 1 - normalized_risk(
        row["slope"],
        df["slope"].min(),
        df["slope"].max(),
    )

    builtup_risk = normalized_risk(
        row["built_up"],
        df["built_up"].min(),
        df["built_up"].max(),
    )

    rainfall_risk = normalized_risk(
        row["rainfall"],
        df["rainfall"].min(),
        df["rainfall"].max(),
    )

    road_risk = normalized_risk(
        row["road_density"],
        df["road_density"].min(),
        df["road_density"].max(),
    )

    factors = {
        "elevation": round(
            elevation_risk * 100,
            2,
        ),
        "slope": round(
            slope_risk * 100,
            2,
        ),
        "built_up": round(
            builtup_risk * 100,
            2,
        ),
        "rainfall": round(
            rainfall_risk * 100,
            2,
        ),
        "road_density": round(
            road_risk * 100,
            2,
        ),
    }

    strongest_factor = max(
        factors,
        key=factors.get,
    )

    factor_names = {
        "elevation": "low elevation",
        "slope": "terrain conditions",
        "built_up": "high built-up intensity",
        "rainfall": "higher rainfall exposure",
        "road_density": "higher road density",
    }

    explanation = (
        f"This location has a "
        f"{row['risk_level'].lower()} "
        f"waterlogging risk with a risk score of "
        f"{row['risk_score']:.2f}. "
        f"The strongest contributing factor in the "
        f"current risk model is "
        f"{factor_names[strongest_factor]}."
    )

    return {
        "location_id": int(
            row["location_id"]
        ),
        "latitude": float(
            row["latitude"]
        ),
        "longitude": float(
            row["longitude"]
        ),
        "risk_score": float(
            row["risk_score"]
        ),
        "risk_level": row["risk_level"],
        "priority": int(
            row["priority"]
        ),

        "factors": {
            "elevation": float(
                row["elevation"]
            ),
            "slope": float(
                row["slope"]
            ),
            "built_up": float(
                row["built_up"]
            ),
            "rainfall": float(
                row["rainfall"]
            ),
            "road_density": float(
                row["road_density"]
            ),
        },

        "factor_risk": factors,

        "strongest_factor": strongest_factor,

        "explanation": explanation,
    }


@app.get("/api/locations/{location_id}")
def location(location_id: int):
    df = load_data()

    result = df[
        df["location_id"] == location_id
    ]

    if result.empty:
        raise HTTPException(
            status_code=404,
            detail="Location not found",
        )

    return result.iloc[0].to_dict()


@app.get("/api/localities")
def localities():
    localities_file = Path(__file__).resolve().parent / "localities.json"
    if localities_file.exists():
        import json
        with open(localities_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}