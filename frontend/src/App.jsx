import { useEffect, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000";

function getRiskColor(level) {
  switch (level) {
    case "Very High":
      return "#ef4444";
    case "High":
      return "#f97316";
    case "Moderate":
      return "#eab308";
    case "Low":
      return "#22c55e";
    default:
      return "#64748b";
  }
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "number") {
    return Number.isInteger(value) ? value : value.toFixed(2);
  }

  return value;
}

function ResizeMap() {
  const map = useMap();

  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 800);

    return () => clearTimeout(timer);
  }, [map]);

  return null;
}

function App() {
  const [dashboardActive, setDashboardActive] = useState(false);
  const [riskLocations, setRiskLocations] = useState([]);
  const [allLocations, setAllLocations] = useState([]);
  const [localities, setLocalities] = useState({});
  const [stats, setStats] = useState(null);
  const [selectedRisk, setSelectedRisk] = useState(null);
  const [selectedExplanation, setSelectedExplanation] = useState(null);
  const [selectedImpact, setSelectedImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError] = useState("");
  const locationAnalysisRef = useRef(null);

  const openDashboard = () => {
    setDashboardActive(true);
  };

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        setError("");

        const [topRiskResponse, statsResponse, localitiesResponse, allLocationsResponse] =
          await Promise.all([
            fetch(`${API_BASE_URL}/api/top-risk`),
            fetch(`${API_BASE_URL}/api/stats`),
            fetch(`${API_BASE_URL}/api/localities`),
            fetch(`${API_BASE_URL}/api/locations`),
          ]);

        if (!topRiskResponse.ok) {
          throw new Error("Unable to load risk locations.");
        }

        if (!statsResponse.ok) {
          throw new Error("Unable to load dashboard statistics.");
        }

        if (!localitiesResponse.ok) {
          throw new Error("Unable to load verified locality names.");
        }

        if (!allLocationsResponse.ok) {
          throw new Error("Unable to load the full risk dataset.");
        }

        const topRiskData = await topRiskResponse.json();
        const statsData = await statsResponse.json();
        const localitiesData = await localitiesResponse.json();
        const allLocationsData = await allLocationsResponse.json();

        const locations = topRiskData.locations || topRiskData || [];
        const localityMap = localitiesData || {};
        const allLocationArray = Array.isArray(allLocationsData)
          ? allLocationsData
          : allLocationsData.locations ||
            allLocationsData.data ||
            allLocationsData.results ||
            [];

        const formattedLocations = locations.map((location) => ({
          id: location.location_id,
          name:
            localityMap[String(location.location_id)] ||
            localityMap[location.location_id] ||
            `Location ${location.location_id}`,
          coordinates: [location.latitude, location.longitude],
          level: location.risk_level,
          score: location.risk_score,
          priority: location.priority,
          color: getRiskColor(location.risk_level),
        }));

        setRiskLocations(formattedLocations);
        setAllLocations(allLocationArray);
        setLocalities(localityMap);
        setStats(statsData);
      } catch (err) {
        console.error(err);
        setError(
          "Could not connect to the FLOWSIGHT backend. Make sure FastAPI is running on port 8000."
        );
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  const selectRiskLocation = async (location) => {
    setSelectedRisk(location);
    setSelectedExplanation(null);
    setSelectedImpact(null);
    setAnalysisLoading(true);

    try {
      const explanationResponse = await fetch(
        `${API_BASE_URL}/api/locations/${location.id}/explanation`
      );

      if (!explanationResponse.ok) {
        throw new Error("Unable to load location analysis.");
      }

      const explanation = await explanationResponse.json();
      setSelectedExplanation(explanation);

      try {
        const impactResponse = await fetch(
          `${API_BASE_URL}/api/locations/${location.id}/impact`
        );

        if (impactResponse.ok) {
          const impact = await impactResponse.json();
          setSelectedImpact(impact);
        } else {
          console.error("Impact API returned an error.");
        }
      } catch (impactError) {
        console.error("Unable to load location impact:", impactError);
      }
    } catch (err) {
      console.error(err);
      setError("Could not load the selected location analysis.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  const scrollToLocationAnalysis = () => {
    requestAnimationFrame(() => {
      locationAnalysisRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const riskDistribution = stats?.risk_distribution || {};
  const averageRisk = stats?.average_risk_score;
  const highestRisk = stats?.highest_risk_score;

  const selectedFactors = selectedExplanation?.factors || {};
  const selectedFactorRisk = selectedExplanation?.factor_risk || {};

  return (
    <div className={`app-shell ${dashboardActive ? "dashboard-active" : ""}`}>
      {/* ================= LANDING PAGE ================= */}
      <section className="landing-page">
        <img
          className="landing-image"
          src="/images/hyd.png"
          alt="Hyderabad Charminar"
        />

        <div className="landing-overlay"></div>

        <header className="landing-header">
          <div className="landing-logo">FLOWSIGHT</div>

          <nav className="landing-nav">
            <a href="#about">About</a>
            <a href="#contact">Contact</a>

            <button type="button" onClick={openDashboard}>
              Sign In
            </button>
          </nav>
        </header>

        <main className="hero-content">
          <p className="hero-eyebrow">URBAN WATERLOGGING INTELLIGENCE</p>

          <h1>See the flood before the street does.</h1>

          <p className="hero-description">
            Location-level waterlogging risk intelligence for a safer, more
            prepared Hyderabad.
          </p>

          <button
            type="button"
            className="get-started-button"
            onClick={openDashboard}
          >
            Get Started <span>→</span>
          </button>
        </main>

        <div className="landing-concepts">
          <span>Analyze</span>
          <span>Locate</span>
          <span>Explain</span>
          <span>Prioritize</span>
          <span>Act</span>
        </div>

        <div className="landing-footer-left">
          A Safer, More Prepared Hyderabad.
        </div>

        <div className="landing-footer-right">Scroll to learn more</div>
      </section>

      {/* ================= DASHBOARD ================= */}
      <section className="dashboard-page">
        <header className="dashboard-header">
          <div className="dashboard-brand">
            <div className="dashboard-logo">FLOWSIGHT</div>
            <div className="dashboard-location">HYDERABAD</div>
          </div>

          <div className="dashboard-status">
            <span className="status-dot"></span>
            API CONNECTED
          </div>
        </header>

        <main className="dashboard-content">
          <div className="dashboard-title-row">
            <div>
              <p className="section-eyebrow">URBAN RISK INTELLIGENCE</p>

              <h2>Hyderabad Overview</h2>

              <p className="dashboard-subtitle">
                Explore location-level waterlogging risk and decision-support
                insights.
              </p>
            </div>

            <div className="demo-badge">Backend model data</div>
          </div>

          {error && <div className="model-note">{error}</div>}

          {/* ================= MAP ================= */}
          <section className="dashboard-card map-card">
            <div className="card-header">
              <div>
                <h3>Risk Map</h3>

                <p>
                  Showing the full risk landscape, with the top-priority
                  locations highlighted.
                </p>
              </div>

              <div className="map-legend">
                <div>
                  <span className="legend-dot red"></span>
                  Very High
                </div>

                <div>
                  <span className="legend-dot orange"></span>
                  High
                </div>

                <div>
                  <span className="legend-dot yellow"></span>
                  Moderate
                </div>

                <div>
                  <span className="legend-dot green"></span>
                  Low
                </div>
              </div>
            </div>

            <div className="map-wrapper">
              <MapContainer
                center={[17.385, 78.4867]}
                zoom={12}
                scrollWheelZoom={true}
                className="risk-map"
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <ResizeMap />

                {allLocations
                  .filter(
                    (location) =>
                      !riskLocations.some(
                        (topLocation) =>
                          String(topLocation.id) === String(location.location_id)
                      )
                  )
                  .map((location) => {
                    const color = getRiskColor(location.risk_level);
                    const locationName =
                      localities[String(location.location_id)] ||
                      localities[location.location_id] ||
                      `Location ${location.location_id}`;

                    const mapLocation = {
                      id: location.location_id,
                      name: locationName,
                      coordinates: [location.latitude, location.longitude],
                      level: location.risk_level,
                      score: location.risk_score,
                      priority: location.priority,
                      color,
                    };

                    return (
                      <CircleMarker
                        key={`overview-${location.location_id}`}
                        center={[location.latitude, location.longitude]}
                        radius={3}
                        pathOptions={{
                          color,
                          fillColor: color,
                          fillOpacity: 0.45,
                          weight: 0,
                        }}
                        eventHandlers={{
                          click: () => selectRiskLocation(mapLocation),
                        }}
                      >
                        <Popup className="risk-popup">
                          <div className="popup-content">
                            <div className="popup-label">ANALYSIS LOCATION</div>

                            <h3>{locationName}</h3>

                            <div className="popup-risk-row">
                              <div>
                                <span className="popup-small-label">
                                  RISK LEVEL
                                </span>

                                <strong style={{ color }}>
                                  {location.risk_level}
                                </strong>
                              </div>

                              <div>
                                <span className="popup-small-label">
                                  RISK SCORE
                                </span>

                                <strong>
                                  {formatValue(location.risk_score)}/100
                                </strong>
                              </div>
                            </div>

                            <div className="popup-priority">
                              <span>Priority</span>
                              <strong>#{location.priority}</strong>
                            </div>

                            <div className="popup-action">
                              <span className="popup-action-label">
                                LOCATION ID
                              </span>
                              <p>{location.location_id}</p>
                            </div>

                            <button
                              type="button"
                              className="popup-analysis-button"
                              onClick={() => {
                                selectRiskLocation(mapLocation);
                                scrollToLocationAnalysis();
                              }}
                            >
                              View Full Analysis →
                            </button>
                          </div>
                        </Popup>
                      </CircleMarker>
                    );
                  })}

                {riskLocations.map((location) => (
                  <CircleMarker
                    key={location.id}
                    center={location.coordinates}
                    radius={10}
                    pathOptions={{
                      color: location.color,
                      fillColor: location.color,
                      fillOpacity: 0.9,
                      weight: 3,
                    }}
                    eventHandlers={{
                      click: () => selectRiskLocation(location),
                    }}
                  >
                    <Popup className="risk-popup">
                      <div className="popup-content">
                        <div className="popup-label">RISK LOCATION</div>

                        <h3>{location.name}</h3>

                        <div className="popup-risk-row">
                          <div>
                            <span className="popup-small-label">RISK LEVEL</span>

                            <strong style={{ color: location.color }}>
                              {location.level}
                            </strong>
                          </div>

                          <div>
                            <span className="popup-small-label">RISK SCORE</span>

                            <strong>{formatValue(location.score)}/100</strong>
                          </div>
                        </div>

                        <div className="popup-priority">
                          <span>Priority</span>
                          <strong>#{location.priority}</strong>
                        </div>

                        <button
                          type="button"
                          className="popup-analysis-button"
                          onClick={() => {
                                selectRiskLocation(location);
                                scrollToLocationAnalysis();
                              }}
                        >
                          View Full Analysis →
                        </button>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </MapContainer>
            </div>

            <div className="map-demo-note">
              {loading
                ? "Loading risk locations from the FLOWSIGHT backend..."
                : `${allLocations.length || stats?.total_locations || 0} analysis locations shown, with the top ${riskLocations.length} priority locations highlighted.`}
            </div>
          </section>

          {/* ================= LOCATION ANALYSIS ================= */}
          <section
            ref={locationAnalysisRef}
            className="dashboard-card location-analysis"
          >
            <div className="card-header">
              <div>
                <p className="section-eyebrow">LOCATION ANALYSIS</p>

                <h3>
                  {selectedRisk ? selectedRisk.name : "Select a risk location"}
                </h3>

                <p>
                  {selectedRisk
                    ? "Risk intelligence and contributing factors for this location."
                    : "Click a risk marker on the map to explore its details."}
                </p>
              </div>
            </div>

            {selectedRisk ? (
              <div className="analysis-content">
                {analysisLoading ? (
                  <div className="empty-analysis">
                    <p>Loading location analysis...</p>
                  </div>
                ) : selectedExplanation ? (
                  <>
                    <div className="analysis-summary">
                      <div className="score-box">
                        <span>RISK SCORE</span>
                        <strong>{formatValue(selectedExplanation.risk_score)}</strong>
                        <small>/ 100</small>
                      </div>

                      <div className="summary-details">
                        <div>
                          <span>Risk Level</span>
                          <strong
                            style={{
                              color: getRiskColor(selectedExplanation.risk_level),
                            }}
                          >
                            {selectedExplanation.risk_level}
                          </strong>
                        </div>

                        <div>
                          <span>Priority</span>
                          <strong>#{selectedExplanation.priority}</strong>
                        </div>
                      </div>
                    </div>

                    <div className="analysis-grid">
                      <div className="factors-section">
                        <h4>Contributing Factors</h4>

                        <div className="factor-list">
                          <div>
                            <span>Elevation</span>
                            <strong>{formatValue(selectedFactors.elevation)}</strong>
                            <small>
                              Risk contribution: {formatValue(selectedFactorRisk.elevation)}
                            </small>
                          </div>

                          <div>
                            <span>Built-up Area</span>
                            <strong>{formatValue(selectedFactors.built_up)}</strong>
                            <small>
                              Risk contribution: {formatValue(selectedFactorRisk.built_up)}
                            </small>
                          </div>

                          <div>
                            <span>Slope</span>
                            <strong>{formatValue(selectedFactors.slope)}</strong>
                            <small>
                              Risk contribution: {formatValue(selectedFactorRisk.slope)}
                            </small>
                          </div>

                          <div>
                            <span>Rainfall</span>
                            <strong>{formatValue(selectedFactors.rainfall)}</strong>
                            <small>
                              Risk contribution: {formatValue(selectedFactorRisk.rainfall)}
                            </small>
                          </div>

                          <div>
                            <span>Road Density</span>
                            <strong>{formatValue(selectedFactors.road_density)}</strong>
                            <small>
                              Risk contribution: {formatValue(selectedFactorRisk.road_density)}
                            </small>
                          </div>
                        </div>
                      </div>

                      <div className="action-section">
                        <div className="action-icon">→</div>

                        <div>
                          <span>MODEL EXPLANATION</span>

                          <h4>Why is this location at risk?</h4>

                          <p>{selectedExplanation.explanation}</p>

                          <p>
                            Strongest contributing factor: {" "}
                            <strong>
                              {selectedExplanation.strongest_factor || "—"}
                            </strong>
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="model-note">
                      Risk score and factor contributions are populated directly
                      from the FLOWSIGHT backend model output.
                    </div>

                    <div className="impact-analysis-section">
                      <div className="impact-section-header">
                        <div>
                          <span>SPATIAL IMPACT</span>
                          <h4>Potential Impact Around This Location</h4>
                        </div>

                        <div className="impact-radius">
                          <span>INSPECTION RADIUS</span>
                          <strong>
                            {formatValue(
                              selectedImpact?.impact_radius?.recommended_radius_km
                            )}{" "}
                            km
                          </strong>
                        </div>
                      </div>

                      <div className="impact-grid">
                        <div className="impact-panel">
                          <span>NEARBY EXPOSURE</span>

                          {selectedImpact?.nearby_exposure?.locations?.length ? (
                            <div className="impact-list">
                              {selectedImpact.nearby_exposure.locations
                                .slice(0, 3)
                                .map((point) => (
                                  <div
                                    className="impact-list-item"
                                    key={point.location_id}
                                  >
                                    <div>
                                      <strong>
                                        {localities[String(point.location_id)] ||
                                          localities[point.location_id] ||
                                          `Analysis Point ${point.location_id}`}
                                      </strong>

                                      <small>
                                        {formatValue(point.distance_km)} km away
                                      </small>
                                    </div>

                                    <strong
                                      style={{
                                        color: getRiskColor(point.risk_level),
                                      }}
                                    >
                                      {formatValue(point.risk_score)}
                                    </strong>
                                  </div>
                                ))}
                            </div>
                          ) : (
                            <p className="impact-empty">
                              No nearby exposure points returned.
                            </p>
                          )}
                        </div>

                        <div className="impact-panel">
                          <span>RISK CORRIDOR</span>

                          {selectedImpact?.route_exposure?.nearby_corridors?.length ? (
                            <div className="impact-list">
                              {selectedImpact.route_exposure.nearby_corridors
                                .slice(0, 3)
                                .map((corridor) => (
                                  <div
                                    className="impact-list-item"
                                    key={corridor.corridor_id}
                                  >
                                    <div>
                                      <strong>{corridor.name}</strong>

                                      <small>
                                        {corridor.exposure_level}
                                      </small>
                                    </div>

                                    <strong>
                                      {formatValue(corridor.average_risk_score)}
                                    </strong>
                                  </div>
                                ))}
                            </div>
                          ) : (
                            <p className="impact-empty">
                              No nearby risk corridor returned.
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="field-actions-panel">
                        <span>RECOMMENDED FIELD ACTION</span>

                        {selectedImpact?.action?.recommended ? (
                          <p>{selectedImpact.action.recommended}</p>
                        ) : (
                          <p className="impact-empty">
                            No field action returned for this location.
                          </p>
                        )}
                      </div>

                      <div className="model-note">
                        Spatial impact and corridor exposure are analytical estimates
                        from the current FLOWSIGHT risk model. They do not represent
                        observed flood extent, real-time sensor measurements, or
                        guaranteed road flooding.
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="empty-analysis">
                    <p>No analysis was returned for this location.</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-analysis">
                <div className="empty-analysis-icon">⌖</div>

                <p>
                  Select a risk marker on the map to view location-specific
                  risk intelligence and contributing factors.
                </p>
              </div>
            )}
          </section>

          {/* ================= RISK DISTRIBUTION ================= */}
          <section className="dashboard-card distribution-card">
            <div className="card-header">
              <div>
                <p className="section-eyebrow">CITY-WIDE VIEW</p>

                <h3>Risk Distribution</h3>

                <p>Current distribution across all {stats?.total_locations ?? "the available"} analysis locations.</p>
              </div>
            </div>

            <div className="distribution-grid">
              <div className="distribution-item">
                <span className="distribution-dot red"></span>
                <div>
                  <strong>Very High</strong>
                  <small>{riskDistribution.Very_High ?? riskDistribution["Very High"] ?? 0} locations</small>
                </div>
              </div>

              <div className="distribution-item">
                <span className="distribution-dot orange"></span>
                <div>
                  <strong>High</strong>
                  <small>{riskDistribution.High ?? 0} locations</small>
                </div>
              </div>

              <div className="distribution-item">
                <span className="distribution-dot yellow"></span>
                <div>
                  <strong>Moderate</strong>
                  <small>{riskDistribution.Moderate ?? 0} locations</small>
                </div>
              </div>

              <div className="distribution-item">
                <span className="distribution-dot green"></span>
                <div>
                  <strong>Low</strong>
                  <small>{riskDistribution.Low ?? 0} locations</small>
                </div>
              </div>
            </div>

            <div className="distribution-grid" style={{ marginTop: "18px" }}>
              <div className="distribution-item">
                <div>
                  <strong>Average Risk</strong>
                  <small>{formatValue(averageRisk)} / 100</small>
                </div>
              </div>

              <div className="distribution-item">
                <div>
                  <strong>Highest Risk</strong>
                  <small>{formatValue(highestRisk)} / 100</small>
                </div>
              </div>
            </div>
          </section>
        </main>
      </section>
    </div>
  );
}

export default App;