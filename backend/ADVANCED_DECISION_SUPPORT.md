# FLOWSIGHT — Advanced Decision-Support Features

This document details the architecture, mathematical formulations, API contracts, and data honesty constraints for FLOWSIGHT's three advanced decision-support layers:
1. **Historical Comparison & Event Replay**
2. **Potential Drainage Bottleneck Detection**
3. **Action Priority Dashboard**

---

## 1. Baseline Model Context

FLOWSIGHT evaluates urban waterlogging risk across 1,013 spatial analysis points throughout Hyderabad (~500m grid resolution, ~0.25 km² per point). The baseline model calculates a multi-factor risk score ($0-100$):

$$\text{Risk Score} = \left( 0.25 \times \text{ElevationRisk} + 0.20 \times \text{SlopeRisk} + 0.25 \times \text{BuiltUpRisk} + 0.20 \times \text{RainfallRisk} + 0.10 \times \text{RoadDensityRisk} \right) \times 100$$

Risk levels are categorized as:
- **Low**: Score $< 25.0$
- **Moderate**: $25.0 \le \text{Score} < 50.0$
- **High**: $50.0 \le \text{Score} < 75.0$
- **Very High**: $\text{Score} \ge 75.0$

---

## 2. Feature 1: Historical Comparison / Event Replay

### 2.1 Purpose & Methodology
Municipal leaders and disaster response coordinators need to evaluate:
> *"How does citywide waterlogging risk evolve under different rainfall shocks, and which neighborhoods cross into critical exposure?"*

FLOWSIGHT provides deterministic scenario simulations that model stress-tests against the baseline 1,013-location dataset. 

> [!IMPORTANT]
> **Data Honesty Guarantee**: Scenarios are explicitly designated as **Model Scenarios** or **Event Replays**. They represent mathematical rainfall sensitivity simulations based on the baseline risk index. They do **not** represent observed historical flood sensors, gauge telemetry, or surveyed water depths.

### 2.2 Pre-Configured Scenarios
1. **Intense Cloudburst Scenario (`heavy_downpour_120`)**:
   - Multiplier: $1.20\times$ (+20% citywide rainfall surge).
   - Simulates sudden high-intensity convective cloudburst conditions across all urban catchments.
2. **Severe Monsoon Storm Scenario (`extreme_monsoon_150`)**:
   - Multiplier: $1.50\times$ (+50% monsoon depression).
   - Models citywide saturation and identifies catchments transitioning into High and Very High risk.
3. **October 2020 Synoptic Rain Pattern — Model Replay (`historical_replay_2020_model`)**:
   - Multiplier: $1.80\times$ peak with synoptic spatial distribution (eastern and central basin concentration).
   - Replicates the spatial rainfall intensity pattern of the October 2020 depression. It is strictly an analytical model replay.
4. **Central Basin Flash Storm (`localized_flash_storm`)**:
   - Multiplier: $1.40\times$ localized boost concentrated in low-elevation central catchments along the Musi river corridor.

### 2.3 Mathematical Formulation
For each point $i$, the scenario rainfall is computed:
$$\text{Rainfall}_{\text{scenario}, i} = \text{Rainfall}_{\text{baseline}, i} \times M_i$$

The normalized rainfall risk component is scaled relative to baseline calibration bounds:
$$\text{RainfallRisk}_{\text{scenario}, i} = \operatorname{clip}\left(\frac{\text{Rainfall}_{\text{scenario}, i} - \text{Rainfall}_{\min}}{\text{Rainfall}_{\max} - \text{Rainfall}_{\min}}, 0.0, 2.5\right)$$

Scenario risk is recomputed using the original feature weights and capped between $[0, 100]$:
$$\text{Risk}_{\text{scenario}, i} = \operatorname{clip}\left(\left(0.25 \times \text{ElevRisk}_i + 0.20 \times \text{SlopeRisk}_i + 0.25 \times \text{BuiltUpRisk}_i + 0.20 \times \text{RainfallRisk}_{\text{scenario}, i} + 0.10 \times \text{RoadRisk}_i\right) \times 100, 0, 100\right)$$

### 2.4 API Endpoints
- `GET /api/scenarios`: Returns the catalog of scenarios with metadata, average risk, and affected counts.
- `GET /api/scenarios/{scenario_id}`: Returns scenario configuration, risk distribution, and top affected locations.
- `GET /api/scenarios/{scenario_id}/compare`: Compares scenario vs baseline (average risk delta, max risk delta, newly elevated hotspots that crossed into High/Very High, and top changed locations).

---

## 3. Feature 2: Potential Drainage Bottleneck Detection

### 3.1 Purpose & Methodology
Rather than evaluating hotspots in isolation, municipal field teams require answers to:
> *"Where are multiple risk signals and transit corridors converging spatially?"*

FLOWSIGHT uses a spatial clustering system to delineate **Potential Drainage Bottleneck Zones** (or **Spatial Risk Convergence Zones**).

> [!NOTE]
> **Data Honesty Guarantee**: Terminology is strictly restricted to "Potential Drainage Bottleneck Zones" or "Spatial Risk Convergence Zones". The model identifies geographic convergence of high surface risk and exposed transit corridors; it does **not** claim knowledge of underground pipe blockages or surveyed pipe conditions.

### 3.2 Spatial Clustering Algorithm
1. **Filter High-Risk Points**: Select locations where $\text{risk\_score} \ge \text{min\_risk}$ (default $60.0$).
2. **Spatial Clustering**: Seeded at peak risk points, identify all proximate high-risk points within Haversine distance threshold $\text{radius\_km}$ (default $1.5\text{ km}$).
3. **Centroid Calculation**: Compute centroid $(\bar{\phi}, \bar{\lambda})$ weighted by risk score:
   $$\bar{\phi} = \frac{\sum_i w_i \phi_i}{\sum_i w_i}, \quad \bar{\lambda} = \frac{\sum_i w_i \lambda_i}{\sum_i w_i}$$
4. **Cluster Radius**: $R_{\text{cluster}} = \max(0.5, \max(d_i) + 0.25\text{ km})$.
5. **Route Convergence**: Count intersecting or proximate transit corridors from the ranked corridors engine ($d \le R + 0.5\text{ km}$).
6. **Affected Area Estimate**: $A_{\text{est}} = N_{\text{locations}} \times 0.25\text{ km}^2$.
7. **Bottleneck Score Formulation**:
   $$\text{Base Risk} = 0.40 \times \bar{\text{Risk}} + 0.25 \times \text{MaxRisk}$$
   $$\text{Density Bonus} = \min(20.0, N_{\text{locations}} \times 2.0)$$
   $$\text{Corridor Bonus} = \min(15.0, N_{\text{routes}} \times 3.0)$$
   $$\text{Bottleneck Score} = \min(100.0, \text{Base Risk} + \text{Density Bonus} + \text{Corridor Bonus})$$
8. **Ranking**: Ranked by `bottleneck_score` descending to assign Priority #1, #2, etc.

### 3.3 API Endpoints
- `GET /api/impact/bottlenecks?min_risk=60.0&radius=1.5&limit=10`: Returns list of ranked bottleneck clusters.
- `GET /api/impact/bottlenecks/{bottleneck_id}`: Returns complete cluster details, member locations, nearby routes, polygon geometry, and recommended field inspection action.

---

## 4. Feature 3: Action Priority Dashboard

### 4.1 Purpose & Decision-Support Formula
Answers the core municipal operations question:
> *"Which locations should field teams investigate first?"*

The **Priority Index** ($0 - 100$) integrates six distinct analytical dimensions without fabricating external telemetry:

| Factor | Weight | Component Calculation | Normalization ($0-100$) |
|---|---|---|---|
| **Baseline Risk** | **35%** | Baseline risk score | Direct ($0 - 100$) |
| **Exposure Radius** | **15%** | Recommended influence radius | $\min\left(100, \frac{R_{\text{rec}}}{3.0\text{ km}} \times 100\right)$ |
| **Affected Area** | **15%** | Surrounding elevated points | $\min(100, N_{\text{affected}} \times 10.0)$ |
| **Route Exposure** | **15%** | Proximate risk corridors | $\min(100, N_{\text{routes}} \times 33.33)$ |
| **Bottleneck Concentration** | **10%** | Cluster bottleneck score | Direct ($0 - 100$) |
| **Scenario Sensitivity** | **10%** | Stress-test risk delta $\Delta$ | $\min(100, \Delta_{\text{scenario}} \times 12.5)$ |

$$\begin{aligned}
\text{Priority Index} = &\; 0.35 \times C_{\text{risk}} + 0.15 \times C_{\text{radius}} + 0.15 \times C_{\text{area}} \\
&+ 0.15 \times C_{\text{routes}} + 0.10 \times C_{\text{bottleneck}} + 0.10 \times C_{\text{scenario}}
\end{aligned}$$

### 4.2 Transparent Explanation
Every priority record returns a transparent explanation string detailing why the location was prioritized based on its component factors, alongside recommended inspection guidance (e.g., verifying culvert inlets, clearing roadside silt traps, pre-positioning mobile pumps).

### 4.3 API Endpoints
- `GET /api/priority?limit=10&scenario_id=...`: Returns top priority locations sorted by Priority Index descending.
- `GET /api/priority/{location_id}`: Returns complete priority breakdown, factor contributions, and field action for a single location.

---

## 5. Summary of API Contracts

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/scenarios` | Catalog of available rainfall scenarios & event replays |
| `GET` | `/api/scenarios/{id}` | Scenario configuration & location impact distribution |
| `GET` | `/api/scenarios/{id}/compare` | Baseline vs scenario comparative analysis |
| `GET` | `/api/impact/bottlenecks` | Spatial risk convergence / potential drainage bottleneck zones |
| `GET` | `/api/impact/bottlenecks/{id}` | Complete bottleneck cluster details & contributing points |
| `GET` | `/api/priority` | Action Priority Index ranked list (#1 to #10) |
| `GET` | `/api/priority/{location_id}` | Complete priority breakdown for a single location |

---

## 6. Limitations & Data Honesty Protocol

1. **Analytical Indices**: All risk scores, bottleneck scores, and priority indices are decision-support models based on surface elevation, slope, built-up density, rainfall gradient, and road density.
2. **No Sensor Fabrication**: The system does not claim real-time IoT water depth sensors or live gauge readings.
3. **No Pipe Condition Fabrication**: Bottleneck zones are spatial convergence zones of modeled surface risk, not inspected subterranean pipe blockages.
4. **No Guaranteed Inundation**: Outputs explicitly communicate modeled risk exposure; flooding is never claimed as guaranteed.
5. **Verified Localities**: Locality names are sourced exclusively from `localities.json`. Unmatched points default strictly to `Location {id}` with coordinates.
