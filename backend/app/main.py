import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .impact_engine import impact_engine, classify_exposure, DISCLAIMER_TEXT

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "locations_features.csv"


app = FastAPI(
    title="FLOWSIGHT API",
    description="AI-assisted urban waterlogging risk analysis and spatial impact engine for Hyderabad.",
    version="2.0.0",
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


# =====================================================================
# EXISTING CORE ENDPOINTS (PRESERVED)
# =====================================================================

@app.get("/")
def root():
    return {
        "project": "FLOWSIGHT",
        "status": "online",
        "message": "See the flood before the street does.",
        "capabilities": [
            "risk_scoring",
            "feature_explanation",
            "spatial_impact_radius",
            "affected_areas",
            "route_exposure_corridors",
            "citywide_summary",
            "geojson_export",
        ],
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
            detail=f"Location {location_id} not found",
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


# Feature 7 route placed before {location_id} to avoid any route ambiguity
@app.get("/api/locations/{location_id}/impact")
def location_impact(location_id: int):
    try:
        return impact_engine.get_location_impact(location_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Location {location_id} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error computing impact for location {location_id}: {str(e)}",
        )


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

    row = result.iloc[0]
    return {
        "location_id": int(row["location_id"]),
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "elevation": float(row["elevation"]),
        "slope": float(row["slope"]),
        "built_up": float(row["built_up"]),
        "rainfall": float(row["rainfall"]),
        "road_density": float(row["road_density"]),
        "risk_score": float(row["risk_score"]),
        "risk_level": str(row["risk_level"]),
        "priority": int(row["priority"]),
    }


@app.get("/api/localities")
def localities():
    localities_file = Path(__file__).resolve().parent / "localities.json"
    if localities_file.exists():
        with open(localities_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# =====================================================================
# SPATIAL IMPACT & ROUTE EXPOSURE ENDPOINTS
# =====================================================================

@app.get("/api/impact/areas/{location_id}")
def affected_areas(
    location_id: int,
    radius_km: float = Query(1.0, description="Search radius in kilometers", ge=0.1, le=10.0),
    limit: int = Query(50, description="Max results", ge=1, le=100),
):
    """
    FEATURE 2: Identify surrounding spatial points exposed to elevated risk.
    """
    try:
        return impact_engine.get_affected_areas(
            location_id=location_id,
            radius_km=radius_km,
            limit=limit,
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Location {location_id} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing affected areas: {str(e)}",
        )


@app.get("/api/impact/route")
def route_exposure(
    start_lat: float = Query(..., description="Start latitude (-90 to 90)"),
    start_lon: float = Query(..., description="Start longitude (-180 to 180)"),
    end_lat: float = Query(..., description="End latitude (-90 to 90)"),
    end_lon: float = Query(..., description="End longitude (-180 to 180)"),
    corridor_km: float = Query(0.25, description="Corridor search buffer in km", ge=0.05, le=2.0),
    samples: int = Query(50, description="Interpolation sample points", ge=10, le=200),
):
    """
    FEATURE 3: Analyze exposure along a route/corridor between two coordinates.
    """
    if not (-90.0 <= start_lat <= 90.0 and -90.0 <= end_lat <= 90.0):
        raise HTTPException(
            status_code=400,
            detail="Latitude must be between -90 and 90 degrees.",
        )
    if not (-180.0 <= start_lon <= 180.0 and -180.0 <= end_lon <= 180.0):
        raise HTTPException(
            status_code=400,
            detail="Longitude must be between -180 and 180 degrees.",
        )

    try:
        return impact_engine.analyze_route(
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            corridor_km=corridor_km,
            samples=samples,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing route exposure: {str(e)}",
        )


@app.get("/api/impact/routes")
def ranked_routes(
    limit: int = Query(10, description="Max ranked corridors to return", ge=1, le=50),
):
    """
    FEATURE 4: Rank potential risk corridors across the FLOWSIGHT grid.
    """
    try:
        corridors = impact_engine.get_ranked_corridors(limit=limit)
        return {
            "count": len(corridors),
            "limit": limit,
            "corridors": corridors,
            "disclaimer": DISCLAIMER_TEXT,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ranking corridors: {str(e)}",
        )


@app.get("/api/impact/summary")
def impact_summary():
    """
    FEATURE 5: Citywide spatial impact summary based on existing 1,013 points.
    """
    try:
        return impact_engine.get_summary()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating impact summary: {str(e)}",
        )


@app.get("/api/impact/geojson")
def impact_geojson(
    include_points: bool = Query(True, description="Include risk points"),
    include_corridors: bool = Query(True, description="Include risk corridors"),
    include_influence_areas: bool = Query(True, description="Include influence area polygons"),
    top_n_hotspots: int = Query(15, description="Top hotspots for influence polygons", ge=1, le=50),
    min_risk: float = Query(0.0, description="Minimum risk score threshold", ge=0.0, le=100.0),
):
    """
    FEATURE 6: Export valid GeoJSON FeatureCollection for frontend visualization.
    """
    try:
        return impact_engine.get_geojson(
            include_points=include_points,
            include_corridors=include_corridors,
            include_influence_areas=include_influence_areas,
            top_n_hotspots=top_n_hotspots,
            min_risk=min_risk,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating GeoJSON: {str(e)}",
        )