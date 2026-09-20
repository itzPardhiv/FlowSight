import math
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

# Earth radius in kilometers (WGS-84 mean radius)
EARTH_RADIUS_KM = 6371.0088


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great circle distance between two points
    on the Earth in kilometers using the Haversine formula.
    """
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(float(EARTH_RADIUS_KM * c), 4)


def distance_matrix(
    coords1: List[Tuple[float, float]] | np.ndarray,
    coords2: List[Tuple[float, float]] | np.ndarray,
) -> np.ndarray:
    """
    Vectorized calculation of pairwise Haversine distances in kilometers.
    coords1: (M, 2) array of (latitude, longitude)
    coords2: (N, 2) array of (latitude, longitude)
    Returns: (M, N) array of distances in km.
    """
    c1 = np.asarray(coords1, dtype=np.float64)
    c2 = np.asarray(coords2, dtype=np.float64)

    if c1.ndim == 1:
        c1 = c1.reshape(1, 2)
    if c2.ndim == 1:
        c2 = c2.reshape(1, 2)

    lat1 = np.radians(c1[:, 0])[:, np.newaxis]  # (M, 1)
    lon1 = np.radians(c1[:, 1])[:, np.newaxis]  # (M, 1)

    lat2 = np.radians(c2[:, 0])[np.newaxis, :]  # (1, N)
    lon2 = np.radians(c2[:, 1])[np.newaxis, :]  # (1, N)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    )
    # Clip for numerical stability
    a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return np.round(EARTH_RADIUS_KM * c, 4)


def interpolate_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    samples: int = 50,
) -> List[Dict[str, Any]]:
    """
    Generate evenly spaced interpolation points along the line
    between start and end coordinates.
    """
    if samples < 2:
        samples = 2

    lats = np.linspace(start_lat, end_lat, samples)
    lons = np.linspace(start_lon, end_lon, samples)

    points = []
    for seq, (lat, lon) in enumerate(zip(lats, lons), start=1):
        points.append(
            {
                "sequence": seq,
                "latitude": round(float(lat), 6),
                "longitude": round(float(lon), 6),
            }
        )
    return points


def points_within_radius(
    df: pd.DataFrame,
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> pd.DataFrame:
    """
    Calculate distances from center_lat/lon to all points in df,
    and return rows with distance_km <= radius_km, sorted by distance.
    """
    if df.empty:
        return df.copy()

    coords = df[["latitude", "longitude"]].values
    center = np.array([[center_lat, center_lon]])
    distances = distance_matrix(center, coords)[0]

    result = df.copy()
    result["distance_km"] = distances
    filtered = result[result["distance_km"] <= radius_km].copy()
    return filtered


def nearest_location(
    df: pd.DataFrame,
    lat: float,
    lon: float,
) -> Tuple[Dict[str, Any], float]:
    """
    Find the single nearest location in df to the given coordinates.
    Returns: (record_dict, distance_km)
    """
    if df.empty:
        raise ValueError("Cannot search nearest location in empty dataset")

    coords = df[["latitude", "longitude"]].values
    target = np.array([[lat, lon]])
    distances = distance_matrix(target, coords)[0]
    min_idx = int(np.argmin(distances))
    min_dist = float(distances[min_idx])

    record = df.iloc[min_idx].to_dict()
    return record, min_dist


def generate_circle_polygon(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    num_points: int = 32,
) -> List[List[float]]:
    """
    Generate polygon coordinates (GeoJSON [lon, lat] format) approximating
    a geodesic circle of radius_km around (center_lat, center_lon).
    """
    coords: List[List[float]] = []
    r_lat = radius_km / EARTH_RADIUS_KM  # angular distance in radians

    center_lat_rad = math.radians(center_lat)
    center_lon_rad = math.radians(center_lon)

    for i in range(num_points):
        bearing = 2.0 * math.pi * i / num_points
        pt_lat_rad = math.asin(
            math.sin(center_lat_rad) * math.cos(r_lat)
            + math.cos(center_lat_rad) * math.sin(r_lat) * math.cos(bearing)
        )
        pt_lon_rad = center_lon_rad + math.atan2(
            math.sin(bearing) * math.sin(r_lat) * math.cos(center_lat_rad),
            math.cos(r_lat) - math.sin(center_lat_rad) * math.sin(pt_lat_rad),
        )

        pt_lat = math.degrees(pt_lat_rad)
        pt_lon = math.degrees(pt_lon_rad)
        coords.append([round(pt_lon, 6), round(pt_lat, 6)])

    # Close polygon
    coords.append(coords[0])
    return coords
