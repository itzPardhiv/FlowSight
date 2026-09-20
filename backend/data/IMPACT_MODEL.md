# FLOWSIGHT Spatial Impact & Route Exposure Model

## 1. Purpose
The **FLOWSIGHT Spatial Impact & Route Exposure Model** expands FLOWSIGHT from pointwise risk classification to continuous spatial impact assessment and transit corridor exposure estimation. It allows municipal teams, disaster response coordinators, and urban planners to evaluate surrounding risk footprints and analyze spatial corridors across Hyderabad's analyzed urban surface.

---

## 2. Existing FLOWSIGHT Risk Model
FLOWSIGHT models baseline waterlogging susceptibility across 1,013 spatial points using an empirical decision-support index:

$$\text{Risk Score} = \left( 0.25 \times (1 - \text{Norm}(\text{Elevation})) + 0.20 \times (1 - \text{Norm}(\text{Slope})) + 0.25 \times \text{Norm}(\text{BuiltUp}) + 0.20 \times \text{Norm}(\text{Rainfall}) + 0.10 \times \text{Norm}(\text{RoadDensity}) \right) \times 100$$

> **Important**: This model provides an analytical spatial decision-support index, **not** an empirical hydraulic simulation or historical flood probability.

---

## 3. Haversine Distance Calculation
Geographic distances across the surface are computed using the spherical Haversine formula assuming Earth radius $R = 6371.0088\text{ km}$:

$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)$$
$$c = 2 \cdot \operatorname{atan2}\left(\sqrt{a}, \sqrt{1 - a}\right)$$
$$d = R \cdot c$$

Where $\phi_1, \phi_2$ are latitudes and $\lambda_1, \lambda_2$ are longitudes in radians.

---

## 4. Impact Radius Methodology
For any identified hotspot, the model assesses spatial influence across concentric analytical bands:
- **0.5 km** (immediate localized catchment)
- **1.0 km** (proximate neighborhood footprint)
- **2.0 km** (ward-scale influence)
- **3.0 km** (sub-basin influence)
- **5.0 km** (macro-scale urban corridor)

Each radius band computes:
* Sampled location count ($N$)
* Average risk score
* Maximum risk score
* Count of High Risk ($\ge 60$) and Very High Risk ($\ge 75$) points
* Analytical exposure classification

The recommended impact radius is derived from the decay profile of high-risk density rather than a static arbitrary number.

---

## 5. Route & Corridor Exposure Methodology
Because a verified vector road graph is not yet bundled in the local dataset, FLOWSIGHT evaluates **Spatial Risk Corridors**:
1. Linear/geodesic discretization of the path between start and end coordinates into $N$ sample waypoints ($10 \le N \le 200$).
2. Spatial buffer aggregation within a configurable corridor width ($0.05 \le \text{corridor\_km} \le 2.0$).
3. Distance-weighted nearest-neighbor risk interpolation.
4. Composite segment scoring and corridor risk ranking.

Corridors are labeled analytically as `Risk Corridor 1`, `Risk Corridor 2`, etc.

---

## 6. Exposure Classification
Exposure categories strictly map to the normalized risk scale:

| Risk Score Range | Exposure Classification | Recommended Priority / Action |
|---|---|---|
| **$\ge 75.0$** | **Very High Exposure** | Priority 1 inspection; immediate drain clearing & pump positioning |
| **$60.0 - 74.99$** | **High Exposure** | Priority 2 inspection; runoff monitoring during heavy showers |
| **$40.0 - 59.99$** | **Moderate Exposure** | Routine maintenance and catchment clearance |
| **$< 40.0$** | **Low Exposure** | Baseline periodic review |

---

## 7. GeoJSON Structure
The `GET /api/impact/geojson` endpoint provides a standard RFC 7946 GeoJSON `FeatureCollection`:
- **Points (`Point`)**: FLOWSIGHT analysis points with risk attributes and terrain features.
- **Influence Polygons (`Polygon`)**: Geodesic circles showing recommended risk influence footprints.
- **Corridors (`LineString`)**: Ranked high-risk spatial transit corridors.

---

## 8. Limitations
- **Resolution**: Point grid spacing is ~0.005° (~500m), representing macro-scale catchment cells (~0.25 km² per point).
- **Static Infiltration**: Subsurface drainage capacity and soil infiltration rates are modeled via built-up proxies.
- **No Real-time Sensors**: Model outputs are synthetic decision-support indicators rather than live telemetry.

---

## 9. Data Honesty Rules
- **No Fabricated Road Names**: Routes are identified by coordinates and analytical corridor IDs.
- **No Fabricated Flood Claims**: Outputs explicitly state "model-estimated exposure" rather than "flooded road" or "flood probability".
- **Transparent Disclaimers**: All responses include explicit provenance and methodology notices.

---

## 10. Future Upgrade Path
- **OpenStreetMap / OSMnx Integration**: Incorporate full road topological graph geometries and node intersections.
- **1D/2D Hydrodynamic Modeling**: Link rainfall runoff with stormwater pipe network capacities (SWMM).
- **IoT Telemetry**: Ingest real-time water level sensor feeds at critical underpasses and nalas.
