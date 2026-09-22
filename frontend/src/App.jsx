import { useEffect, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

import {
  API_BASE_URL,
  getAllLocations,
  getBottlenecks,
  getLocalities,
  getLocationExplanation,
  getLocationImpact,
  getPriorityLocations,
  getRankedRoutes,
  getScenarios,
  compareScenario,
  getStats,
  getTopRisk,
} from "./services/api";

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
  // Existing state
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

  // Feature 1: Scenarios & Event Replay
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("heavy_downpour_120");
  const [scenarioComparison, setScenarioComparison] = useState(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);

  // Feature 2: Potential Drainage Bottlenecks
  const [bottlenecks, setBottlenecks] = useState([]);
  const [selectedBottleneck, setSelectedBottleneck] = useState(null);

  // Feature 3: Action Priority Dashboard
  const [priorities, setPriorities] = useState([]);

  // Corridors (for map)
  const [corridors, setCorridors] = useState([]);

  // Map layer toggles
  const [layerHotspots, setLayerHotspots] = useState(true);
  const [layerBottlenecks, setLayerBottlenecks] = useState(true);
  const [layerCorridors, setLayerCorridors] = useState(false);
  const [layerScenario, setLayerScenario] = useState(false);

  // Navigation & section refs
  const [activeNav, setActiveNav] = useState("overview");
  const mapRef = useRef(null);
  const locationAnalysisRef = useRef(null);
  const scenarioRef = useRef(null);
  const bottleneckRef = useRef(null);
  const priorityRef = useRef(null);
  const distributionRef = useRef(null);
  const methodologyRef = useRef(null);

  const openDashboard = () => {
    setDashboardActive(true);
  };

  const scrollToSection = (ref, navKey) => {
    setActiveNav(navKey);
    requestAnimationFrame(() => {
      ref.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  // Initial dashboard load
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        setError("");

        const [
          topRiskData,
          statsData,
          localitiesData,
          allLocationsData,
          scenariosData,
          bottlenecksData,
          prioritiesData,
          corridorsData,
        ] = await Promise.all([
          getTopRisk(10).catch(() => ({ locations: [] })),
          getStats().catch(() => null),
          getLocalities().catch(() => ({})),
          getAllLocations().catch(() => ({ locations: [] })),
          getScenarios().catch(() => ({ scenarios: [] })),
          getBottlenecks({ limit: 10 }).catch(() => ({ bottlenecks: [] })),
          getPriorityLocations({ limit: 10 }).catch(() => ({ priorities: [] })),
          getRankedRoutes(10).catch(() => ({ corridors: [] })),
        ]);

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

        const loadedScenarios = scenariosData.scenarios || [];
        setScenarios(loadedScenarios);
        if (loadedScenarios.length > 0) {
          setSelectedScenarioId(loadedScenarios[0].scenario_id);
        }

        const loadedBottlenecks = bottlenecksData.bottlenecks || [];
        setBottlenecks(loadedBottlenecks);
        if (loadedBottlenecks.length > 0) {
          setSelectedBottleneck(loadedBottlenecks[0]);
        }

        setPriorities(prioritiesData.priorities || []);
        setCorridors(corridorsData.corridors || []);
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

  // Fetch comparison whenever scenario changes
  useEffect(() => {
    if (!selectedScenarioId) return;

    const loadComparison = async () => {
      try {
        setScenarioLoading(true);
        const comp = await compareScenario(selectedScenarioId);
        setScenarioComparison(comp);
      } catch (err) {
        console.error("Error loading scenario comparison:", err);
      } finally {
        setScenarioLoading(false);
      }
    };

    loadComparison();
  }, [selectedScenarioId]);

  const selectRiskLocation = async (location) => {
    setSelectedRisk(location);
    setSelectedExplanation(null);
    setSelectedImpact(null);
    setAnalysisLoading(true);

    try {
      const explanation = await getLocationExplanation(location.id);
      setSelectedExplanation(explanation);

      try {
        const impact = await getLocationImpact(location.id);
        setSelectedImpact(impact);
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

  const handleSelectChangedLocation = (loc) => {
    const mapLocation = {
      id: loc.location_id,
      name: loc.locality || `Location ${loc.location_id}`,
      coordinates: [loc.latitude, loc.longitude],
      level: loc.scenario_risk_level || loc.baseline_risk_level,
      score: loc.scenario_risk_score || loc.baseline_risk_score,
      priority: 1,
      color: getRiskColor(loc.scenario_risk_level || loc.baseline_risk_level),
    };
    selectRiskLocation(mapLocation);
    scrollToSection(locationAnalysisRef, "overview");
  };

  const riskDistribution = stats?.risk_distribution || {};
  const averageRisk = stats?.average_risk_score;
  const highestRisk = stats?.highest_risk_score;

  const selectedFactors = selectedExplanation?.factors || {};
  const selectedFactorRisk = selectedExplanation?.factor_risk || {};

  const priorityOne = priorities.length > 0 ? priorities[0] : null;
  const otherPriorities = priorities.slice(1);

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

          <nav className="dashboard-nav">
            <button
              type="button"
              className={`nav-btn ${activeNav === "overview" ? "active" : ""}`}
              onClick={() => scrollToSection(mapRef, "overview")}
            >
              Risk Map
            </button>

            <button
              type="button"
              className={`nav-btn ${activeNav === "scenarios" ? "active" : ""}`}
              onClick={() => scrollToSection(scenarioRef, "scenarios")}
            >
              Scenario Analysis
            </button>

            <button
              type="button"
              className={`nav-btn ${activeNav === "bottlenecks" ? "active" : ""}`}
              onClick={() => scrollToSection(bottleneckRef, "bottlenecks")}
            >
              Bottlenecks
            </button>

            <button
              type="button"
              className={`nav-btn ${activeNav === "priority" ? "active" : ""}`}
              onClick={() => scrollToSection(priorityRef, "priority")}
            >
              Action Priority
            </button>

            <button
              type="button"
              className={`nav-btn ${activeNav === "methodology" ? "active" : ""}`}
              onClick={() => scrollToSection(methodologyRef, "methodology")}
            >
              Methodology
            </button>
          </nav>

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

          {/* ================= MAP CARD ================= */}
          <section ref={mapRef} className="dashboard-card map-card">
            <div className="card-header">
              <div>
                <h3>Risk Map</h3>

                <p>
                  Showing the full risk landscape, with spatial convergence
                  zones and multi-layer toggles.
                </p>
              </div>

              <div className="layer-toggles">
                <button
                  type="button"
                  className={`layer-toggle-btn ${layerHotspots ? "active" : ""}`}
                  onClick={() => setLayerHotspots(!layerHotspots)}
                  title="Toggle overview and hotspot locations"
                >
                  <span className="layer-indicator"></span>
                  Risk Hotspots
                </button>

                <button
                  type="button"
                  className={`layer-toggle-btn ${layerBottlenecks ? "active" : ""}`}
                  onClick={() => setLayerBottlenecks(!layerBottlenecks)}
                  title="Toggle potential drainage bottleneck zones"
                >
                  <span className="layer-indicator purple"></span>
                  Bottleneck Zones
                </button>

                <button
                  type="button"
                  className={`layer-toggle-btn ${layerCorridors ? "active" : ""}`}
                  onClick={() => setLayerCorridors(!layerCorridors)}
                  title="Toggle ranked transit risk corridors"
                >
                  <span className="layer-indicator cyan"></span>
                  Risk Corridors
                </button>

                <button
                  type="button"
                  className={`layer-toggle-btn ${layerScenario ? "active" : ""}`}
                  onClick={() => setLayerScenario(!layerScenario)}
                  title="Highlight scenario-elevated hotspots"
                >
                  <span className="layer-indicator"></span>
                  Scenario Elev.
                </button>
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

                {/* Layer 1: Background & Overview Points */}
                {layerHotspots &&
                  allLocations
                    .filter(
                      (location) =>
                        !riskLocations.some(
                          (topLocation) =>
                            String(topLocation.id) ===
                            String(location.location_id)
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
                                  scrollToSection(locationAnalysisRef, "overview");
                                }}
                              >
                                View Full Analysis →
                              </button>
                            </div>
                          </Popup>
                        </CircleMarker>
                      );
                    })}

                {/* Layer 1b: Top-Risk Hotspots */}
                {layerHotspots &&
                  riskLocations.map((location) => (
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
                          <div className="popup-label">TOP RISK HOTSPOT</div>

                          <h3>{location.name}</h3>

                          <div className="popup-risk-row">
                            <div>
                              <span className="popup-small-label">
                                RISK LEVEL
                              </span>

                              <strong style={{ color: location.color }}>
                                {location.level}
                              </strong>
                            </div>

                            <div>
                              <span className="popup-small-label">
                                RISK SCORE
                              </span>

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
                              scrollToSection(locationAnalysisRef, "overview");
                            }}
                          >
                            View Full Analysis →
                          </button>
                        </div>
                      </Popup>
                    </CircleMarker>
                  ))}

                {/* Layer 2: Potential Drainage Bottleneck Zones */}
                {layerBottlenecks &&
                  bottlenecks.map((b) => {
                    const positions = b.polygon_coordinates
                      ? b.polygon_coordinates.map((pt) => [pt[1], pt[0]])
                      : [];

                    return (
                      <Polygon
                        key={b.bottleneck_id}
                        positions={positions}
                        pathOptions={{
                          color: "#c084fc",
                          fillColor: "#a855f7",
                          fillOpacity: 0.18,
                          weight: 2,
                          dashArray: "4 4",
                        }}
                        eventHandlers={{
                          click: () => {
                            setSelectedBottleneck(b);
                            scrollToSection(bottleneckRef, "bottlenecks");
                          },
                        }}
                      >
                        <Popup className="risk-popup">
                          <div className="popup-content">
                            <div className="popup-label">
                              POTENTIAL BOTTLENECK ZONE
                            </div>

                            <h3>{b.name}</h3>

                            <div className="popup-risk-row">
                              <div>
                                <span className="popup-small-label">
                                  BOTTLENECK SCORE
                                </span>
                                <strong style={{ color: "#c084fc" }}>
                                  {formatValue(b.bottleneck_score)}/100
                                </strong>
                              </div>

                              <div>
                                <span className="popup-small-label">
                                  HIGH RISK POINTS
                                </span>
                                <strong>{b.number_of_high_risk_locations}</strong>
                              </div>
                            </div>

                            <div className="popup-priority">
                              <span>Exposed Routes</span>
                              <strong>{b.nearby_route_count}</strong>
                            </div>

                            <button
                              type="button"
                              className="popup-analysis-button"
                              onClick={() => {
                                setSelectedBottleneck(b);
                                scrollToSection(bottleneckRef, "bottlenecks");
                              }}
                            >
                              Inspect Bottleneck Zone →
                            </button>
                          </div>
                        </Popup>
                      </Polygon>
                    );
                  })}

                {/* Layer 3: Risk Corridors */}
                {layerCorridors &&
                  corridors.map((c) => (
                    <Polyline
                      key={c.corridor_id}
                      positions={[
                        [c.start.latitude, c.start.longitude],
                        [c.end.latitude, c.end.longitude],
                      ]}
                      pathOptions={{
                        color: "#38bdf8",
                        weight: 3,
                        opacity: 0.8,
                      }}
                    >
                      <Popup className="risk-popup">
                        <div className="popup-content">
                          <div className="popup-label">RISK CORRIDOR</div>
                          <h3>{c.name}</h3>
                          <div className="popup-risk-row">
                            <div>
                              <span className="popup-small-label">
                                AVG RISK
                              </span>
                              <strong>
                                {formatValue(c.average_risk_score)}
                              </strong>
                            </div>
                            <div>
                              <span className="popup-small-label">
                                EXPOSURE
                              </span>
                              <strong>{c.exposure_level}</strong>
                            </div>
                          </div>
                        </div>
                      </Popup>
                    </Polyline>
                  ))}

                {/* Layer 4: Scenario-Affected Locations */}
                {layerScenario &&
                  scenarioComparison?.newly_elevated_hotspots?.map((loc) => (
                    <CircleMarker
                      key={`scen-elevated-${loc.location_id}`}
                      center={[loc.latitude, loc.longitude]}
                      radius={7}
                      pathOptions={{
                        color: "#ef4444",
                        fillColor: "#f97316",
                        fillOpacity: 0.95,
                        weight: 2,
                      }}
                      eventHandlers={{
                        click: () => handleSelectChangedLocation(loc),
                      }}
                    >
                      <Popup className="risk-popup">
                        <div className="popup-content">
                          <div className="popup-label">NEWLY ELEVATED</div>
                          <h3>{loc.locality}</h3>
                          <div className="popup-risk-row">
                            <div>
                              <span className="popup-small-label">BASELINE</span>
                              <strong>{formatValue(loc.baseline_risk_score)}</strong>
                            </div>
                            <div>
                              <span className="popup-small-label">SCENARIO</span>
                              <strong style={{ color: "#ef4444" }}>
                                {formatValue(loc.scenario_risk_score)} (+{formatValue(loc.risk_delta)})
                              </strong>
                            </div>
                          </div>
                        </div>
                      </Popup>
                    </CircleMarker>
                  ))}
              </MapContainer>
            </div>

            <div className="map-demo-note">
              {loading
                ? "Loading risk locations from the FLOWSIGHT backend..."
                : `${allLocations.length || stats?.total_locations || 0} analysis locations modeled across Hyderabad. Showing ${bottlenecks.length} potential bottleneck convergence zones.`}
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
                            Strongest contributing factor:{" "}
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

          {/* ================= FEATURE 1: SCENARIO ANALYSIS ================= */}
          <section ref={scenarioRef} className="dashboard-card">
            <div className="card-header">
              <div>
                <p className="section-eyebrow">HISTORICAL COMPARISON & EVENT REPLAY</p>
                <h3>Scenario Analysis</h3>
                <p>
                  Compare baseline waterlogging risk against modeled rainfall
                  stress scenarios and synoptic event replays.
                </p>
              </div>

              <div className="demo-badge">Model Scenario / Event Replay</div>
            </div>

            <div className="scenario-card-content">
              {/* Selectable scenario cards */}
              <div className="scenario-selector-grid">
                {scenarios.map((scen) => (
                  <div
                    key={scen.scenario_id}
                    className={`scenario-item ${
                      selectedScenarioId === scen.scenario_id ? "active" : ""
                    }`}
                    onClick={() => setSelectedScenarioId(scen.scenario_id)}
                  >
                    <div>
                      <div className="scenario-item-header">
                        <span className="scenario-type-badge">{scen.type}</span>
                        <span className="scenario-multiplier-badge">
                          {scen.rainfall_multiplier}x Rain
                        </span>
                      </div>
                      <h4>{scen.name}</h4>
                      <p>{scen.description}</p>
                    </div>

                    <div style={{ marginTop: "12px", fontSize: "11px", color: "#64748b" }}>
                      Avg Risk: <strong style={{ color: "#e2e8f0" }}>{formatValue(scen.average_risk)}</strong>
                    </div>
                  </div>
                ))}
              </div>

              {/* Side-by-side comparison KPIs */}
              {scenarioComparison && (
                <>
                  <div className="comparison-kpi-grid">
                    <div className="kpi-card">
                      <span className="kpi-card-label">AVERAGE RISK COMPARISON</span>
                      <div className="kpi-comparison-values">
                        <div className="kpi-values-column">
                          <span className="kpi-subtext">
                            Baseline: <strong>{formatValue(scenarioComparison.baseline_average_risk)}</strong>
                          </span>
                          <span className="kpi-subtext">
                            Scenario: <strong>{formatValue(scenarioComparison.scenario_average_risk)}</strong>
                          </span>
                        </div>
                        <span className="kpi-delta-badge positive">
                          +{formatValue(scenarioComparison.average_risk_delta)}
                        </span>
                      </div>
                    </div>

                    <div className="kpi-card">
                      <span className="kpi-card-label">PEAK RISK COMPARISON</span>
                      <div className="kpi-comparison-values">
                        <div className="kpi-values-column">
                          <span className="kpi-subtext">
                            Baseline: <strong>{formatValue(scenarioComparison.baseline_maximum_risk)}</strong>
                          </span>
                          <span className="kpi-subtext">
                            Scenario: <strong>{formatValue(scenarioComparison.scenario_maximum_risk)}</strong>
                          </span>
                        </div>
                        <span className="kpi-delta-badge positive">
                          +{formatValue(scenarioComparison.maximum_risk_delta)}
                        </span>
                      </div>
                    </div>

                    <div className="kpi-card">
                      <span className="kpi-card-label">SEVERITY ESCALATION</span>
                      <div className="kpi-comparison-values">
                        <div className="kpi-values-column">
                          <span className="kpi-subtext">
                            Locations Elevated: <strong>{scenarioComparison.locations_whose_risk_level_increased}</strong>
                          </span>
                          <span className="kpi-subtext">
                            Locations Decreased: <strong>{scenarioComparison.locations_whose_risk_level_decreased}</strong>
                          </span>
                        </div>
                        <span className="kpi-delta-badge neutral">
                          {scenarioComparison.locations_whose_risk_level_increased} pts
                        </span>
                      </div>
                    </div>

                    <div className="kpi-card">
                      <span className="kpi-card-label">CRITICAL SURGE HOTSPOTS</span>
                      <div className="kpi-comparison-values">
                        <div className="kpi-values-column">
                          <span className="kpi-subtext">
                            New High/Very High: <strong>{scenarioComparison.newly_elevated_hotspots_count}</strong>
                          </span>
                          <span className="kpi-subtext">
                            Total Locations: <strong>{allLocations.length || 1013}</strong>
                          </span>
                        </div>
                        <span className="kpi-delta-badge positive">
                          {scenarioComparison.newly_elevated_hotspots_count} new
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Distribution comparison breakdown */}
                  <div className="distribution-grid" style={{ padding: "0 0 18px", borderBottom: "1px solid rgba(148, 163, 184, 0.1)" }}>
                    <div className="distribution-item">
                      <span className="distribution-dot red"></span>
                      <div>
                        <strong>Very High Risk</strong>
                        <small>
                          {scenarioComparison.baseline_risk_distribution["Very High"]} baseline →{" "}
                          <span style={{ color: "#fca5a5", fontWeight: 700 }}>
                            {scenarioComparison.scenario_risk_distribution["Very High"]} scenario
                          </span>
                        </small>
                      </div>
                    </div>

                    <div className="distribution-item">
                      <span className="distribution-dot orange"></span>
                      <div>
                        <strong>High Risk</strong>
                        <small>
                          {scenarioComparison.baseline_risk_distribution["High"]} baseline →{" "}
                          <span style={{ color: "#fdba74", fontWeight: 700 }}>
                            {scenarioComparison.scenario_risk_distribution["High"]} scenario
                          </span>
                        </small>
                      </div>
                    </div>

                    <div className="distribution-item">
                      <span className="distribution-dot yellow"></span>
                      <div>
                        <strong>Moderate Risk</strong>
                        <small>
                          {scenarioComparison.baseline_risk_distribution["Moderate"]} baseline →{" "}
                          {scenarioComparison.scenario_risk_distribution["Moderate"]} scenario
                        </small>
                      </div>
                    </div>

                    <div className="distribution-item">
                      <span className="distribution-dot green"></span>
                      <div>
                        <strong>Low Risk</strong>
                        <small>
                          {scenarioComparison.baseline_risk_distribution["Low"]} baseline →{" "}
                          {scenarioComparison.scenario_risk_distribution["Low"]} scenario
                        </small>
                      </div>
                    </div>
                  </div>

                  {/* Top changed locations list */}
                  <div className="scenario-tables-grid">
                    <div className="scenario-panel">
                      <div className="scenario-panel-title">
                        <h4>Newly Elevated Hotspots</h4>
                        <span>Transitioned to High/Very High</span>
                      </div>

                      <div className="changed-locations-list">
                        {scenarioComparison.newly_elevated_hotspots?.slice(0, 6).map((loc) => (
                          <div
                            key={`elevated-${loc.location_id}`}
                            className="changed-location-row"
                            onClick={() => handleSelectChangedLocation(loc)}
                            title="Click to view location analysis"
                          >
                            <div className="changed-location-info">
                              <strong>{loc.locality}</strong>
                              <small>
                                {loc.baseline_risk_level} →{" "}
                                <span style={{ color: getRiskColor(loc.scenario_risk_level) }}>
                                  {loc.scenario_risk_level}
                                </span>
                              </small>
                            </div>

                            <div className="changed-location-scores">
                              <span className="score-pill">
                                {formatValue(loc.baseline_risk_score)} → {formatValue(loc.scenario_risk_score)}
                              </span>
                              <span className="delta-pill">+{formatValue(loc.risk_delta)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="scenario-panel">
                      <div className="scenario-panel-title">
                        <h4>Top Changed Locations</h4>
                        <span>Largest Risk Score Increase</span>
                      </div>

                      <div className="changed-locations-list">
                        {scenarioComparison.top_changed_locations?.slice(0, 6).map((loc) => (
                          <div
                            key={`changed-${loc.location_id}`}
                            className="changed-location-row"
                            onClick={() => handleSelectChangedLocation(loc)}
                            title="Click to view location analysis"
                          >
                            <div className="changed-location-info">
                              <strong>{loc.locality}</strong>
                              <small>
                                Risk Score: {formatValue(loc.baseline_risk_score)} → {formatValue(loc.scenario_risk_score)}
                              </small>
                            </div>

                            <div className="changed-location-scores">
                              <span className="delta-pill">+{formatValue(loc.risk_delta)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              )}

              <div className="model-note" style={{ marginTop: "18px" }}>
                Model Scenario / Event Replay: All rainfall modifications and replay events are
                analytical model simulations derived from FLOWSIGHT's baseline risk index. They do
                not represent observed historical flood sensor data or guaranteed inundation extent.
              </div>
            </div>
          </section>

          {/* ================= FEATURE 2: POTENTIAL DRAINAGE BOTTLENECKS ================= */}
          <section ref={bottleneckRef} className="dashboard-card">
            <div className="card-header">
              <div>
                <p className="section-eyebrow">SPATIAL RISK CONVERGENCE</p>
                <h3>Potential Drainage Bottlenecks</h3>
                <p>
                  Identifies clusters where multiple high-risk locations and
                  exposed transit routes converge geographically.
                </p>
              </div>

              <div className="demo-badge">Spatial Risk Convergence Zones</div>
            </div>

            <div className="bottlenecks-content">
              <div className="bottlenecks-grid">
                {bottlenecks.map((b) => (
                  <div
                    key={b.bottleneck_id}
                    className={`bottleneck-card ${
                      selectedBottleneck?.bottleneck_id === b.bottleneck_id ? "active" : ""
                    }`}
                    onClick={() => setSelectedBottleneck(b)}
                  >
                    <div className="bottleneck-card-header">
                      <span className="priority-pill">Priority #{b.priority}</span>
                      <span className="bottleneck-score-badge">
                        {formatValue(b.bottleneck_score)}
                      </span>
                    </div>

                    <h4>{b.name}</h4>

                    <div className="bottleneck-meta-grid">
                      <div className="bottleneck-meta-item">
                        <span>HOTSPOTS</span>
                        <strong>{b.number_of_high_risk_locations} points</strong>
                      </div>

                      <div className="bottleneck-meta-item">
                        <span>AFFECTED AREA</span>
                        <strong>~{formatValue(b.affected_area_estimate)} km²</strong>
                      </div>

                      <div className="bottleneck-meta-item">
                        <span>AVG / PEAK RISK</span>
                        <strong>{formatValue(b.average_risk)} / {formatValue(b.maximum_risk)}</strong>
                      </div>

                      <div className="bottleneck-meta-item">
                        <span>EXPOSED ROUTES</span>
                        <strong>{b.nearby_route_count} corridors</strong>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Selected Bottleneck Inspection Panel */}
              {selectedBottleneck && (
                <div className="bottleneck-inspect-panel">
                  <div className="bottleneck-inspect-header">
                    <div>
                      <span className="section-eyebrow">ZONE INSPECTION DETAILS</span>
                      <h4>{selectedBottleneck.name}</h4>
                    </div>

                    <div className="impact-radius">
                      <span>INFLUENCE RADIUS</span>
                      <strong>{formatValue(selectedBottleneck.radius_km)} km</strong>
                    </div>
                  </div>

                  <div className="impact-grid">
                    <div className="impact-panel">
                      <span>WHERE & WHY FLAGGED</span>
                      <p style={{ margin: "8px 0 0", color: "#cbd5e1", fontSize: "12px", lineHeight: "1.6" }}>
                        {selectedBottleneck.explanation}
                      </p>
                      <small style={{ display: "block", marginTop: "10px", color: "#64748b" }}>
                        Centroid Coordinates: [{selectedBottleneck.center_latitude.toFixed(4)}, {selectedBottleneck.center_longitude.toFixed(4)}]
                      </small>
                    </div>

                    <div className="impact-panel">
                      <span>WHAT SHOULD BE INSPECTED</span>
                      <p style={{ margin: "8px 0 0", color: "#cbd5e1", fontSize: "12px", lineHeight: "1.6" }}>
                        {selectedBottleneck.recommended_action}
                      </p>
                    </div>
                  </div>

                  {selectedBottleneck.contributing_locations && (
                    <div style={{ marginTop: "16px" }}>
                      <span className="section-eyebrow">CONTRIBUTING HIGH-RISK LOCATIONS ({selectedBottleneck.contributing_locations.length})</span>
                      <div className="changed-locations-list" style={{ marginTop: "8px", maxHeight: "190px" }}>
                        {selectedBottleneck.contributing_locations.map((loc) => (
                          <div
                            key={`bn-loc-${loc.location_id}`}
                            className="changed-location-row"
                            onClick={() => {
                              const mapLocation = {
                                id: loc.location_id,
                                name: loc.locality || `Location ${loc.location_id}`,
                                coordinates: [loc.latitude, loc.longitude],
                                level: loc.risk_level,
                                score: loc.risk_score,
                                priority: 1,
                                color: getRiskColor(loc.risk_level),
                              };
                              selectRiskLocation(mapLocation);
                              scrollToSection(locationAnalysisRef, "overview");
                            }}
                          >
                            <div className="changed-location-info">
                              <strong>{loc.locality}</strong>
                              <small>Elevation: {formatValue(loc.elevation)}m • Slope: {formatValue(loc.slope)}°</small>
                            </div>
                            <strong style={{ color: getRiskColor(loc.risk_level), fontSize: "12px" }}>
                              {formatValue(loc.risk_score)}
                            </strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="model-note" style={{ marginTop: "18px" }}>
                Potential Drainage Bottleneck Zone: Analytical spatial clustering of elevated risk
                signals and transit corridor convergence. This model indicates where multiple surface
                runoff and exposure signals concentrate; it does not indicate confirmed subsurface pipe
                blockages, structural drainage failure, or surveyed municipal pipe conditions.
              </div>
            </div>
          </section>

          {/* ================= FEATURE 3: ACTION PRIORITY DASHBOARD ================= */}
          <section ref={priorityRef} className="dashboard-card">
            <div className="card-header">
              <div>
                <p className="section-eyebrow">OPERATIONAL DECISION SUPPORT</p>
                <h3>Action Priority Dashboard</h3>
                <p>
                  Synthesizes Risk + Radius + Affected Area + Route Exposure +
                  Bottleneck Concentration + Scenario Sensitivity into an
                  actionable field inspection index.
                </p>
              </div>

              <div className="demo-badge">Municipal Priority Index</div>
            </div>

            <div className="priority-content">
              {/* Featured Priority #1 Spotlight Card */}
              {priorityOne && (
                <div className="priority-spotlight-card">
                  <div className="spotlight-header">
                    <span className="spotlight-rank-badge">
                      ★ PRIORITY #1 SPOTLIGHT
                    </span>

                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: "9px", color: "#64748b", fontWeight: 700, letterSpacing: "0.12em" }}>
                        PRIORITY INDEX
                      </span>
                      <div style={{ fontSize: "36px", fontWeight: 900, color: "#60a5fa", lineHeight: "1" }}>
                        {formatValue(priorityOne.priority_index)} <small style={{ fontSize: "14px", color: "#64748b" }}>/ 100</small>
                      </div>
                    </div>
                  </div>

                  <div className="spotlight-locality">
                    <h3>{priorityOne.locality}</h3>
                    <p>
                      Coordinates: [{priorityOne.latitude.toFixed(4)}, {priorityOne.longitude.toFixed(4)}] • Location ID: {priorityOne.location_id}
                    </p>
                  </div>

                  <div className="spotlight-metrics-row">
                    <div className="spotlight-metric-box">
                      <span>BASELINE RISK</span>
                      <strong style={{ color: getRiskColor(priorityOne.risk_level) }}>
                        {formatValue(priorityOne.risk_score)}
                      </strong>
                      <small>{priorityOne.risk_level} Risk</small>
                    </div>

                    <div className="spotlight-metric-box">
                      <span>EXPOSURE RADIUS</span>
                      <strong>{formatValue(priorityOne.exposure_radius)} km</strong>
                      <small>Recommended buffer</small>
                    </div>

                    <div className="spotlight-metric-box">
                      <span>AFFECTED AREA</span>
                      <strong>~{formatValue(priorityOne.affected_area)} km²</strong>
                      <small>Surrounding exposure</small>
                    </div>

                    <div className="spotlight-metric-box">
                      <span>EXPOSED ROUTES</span>
                      <strong>{priorityOne.exposed_route_count} corridors</strong>
                      <small>Transit exposure</small>
                    </div>

                    <div className="spotlight-metric-box">
                      <span>BOTTLENECK SCORE</span>
                      <strong style={{ color: "#c084fc" }}>
                        {formatValue(priorityOne.bottleneck_score)}
                      </strong>
                      <small>Spatial convergence</small>
                    </div>
                  </div>

                  <div className="why-prioritized-box">
                    <span>WHY IS THIS LOCATION PRIORITIZED?</span>
                    <p>{priorityOne.explanation}</p>
                  </div>

                  <div className="field-actions-panel" style={{ marginTop: "14px" }}>
                    <span>RECOMMENDED FIELD ACTION</span>
                    <p>{priorityOne.recommended_action}</p>
                  </div>

                  <button
                    type="button"
                    className="get-started-button"
                    style={{ marginTop: "18px", padding: "11px 20px", fontSize: "12px" }}
                    onClick={() => {
                      const mapLocation = {
                        id: priorityOne.location_id,
                        name: priorityOne.locality,
                        coordinates: [priorityOne.latitude, priorityOne.longitude],
                        level: priorityOne.risk_level,
                        score: priorityOne.risk_score,
                        priority: 1,
                        color: getRiskColor(priorityOne.risk_level),
                      };
                      selectRiskLocation(mapLocation);
                      scrollToSection(locationAnalysisRef, "overview");
                    }}
                  >
                    Inspect in Detail →
                  </button>
                </div>
              )}

              {/* Priorities #2 to #10 Grid Cards */}
              <div className="priorities-list-grid">
                {otherPriorities.map((item) => (
                  <div key={item.location_id} className="priority-item-card">
                    <div className="priority-item-header">
                      <span className="priority-rank-chip">Priority #{item.priority_rank}</span>
                      <strong style={{ fontSize: "16px", color: "#60a5fa" }}>
                        {formatValue(item.priority_index)} <small style={{ fontSize: "10px", color: "#64748b" }}>/ 100</small>
                      </strong>
                    </div>

                    <h4>{item.locality}</h4>

                    <div className="priority-item-scores">
                      <span>
                        Risk: <strong style={{ color: getRiskColor(item.risk_level) }}>{formatValue(item.risk_score)}</strong>
                      </span>
                      <span>
                        Area: <strong>~{formatValue(item.affected_area)} km²</strong>
                      </span>
                      <span>
                        Radius: <strong>{formatValue(item.exposure_radius)} km</strong>
                      </span>
                    </div>

                    <p className="priority-action-text">{item.recommended_action}</p>

                    <button
                      type="button"
                      className="popup-analysis-button"
                      onClick={() => {
                        const mapLocation = {
                          id: item.location_id,
                          name: item.locality,
                          coordinates: [item.latitude, item.longitude],
                          level: item.risk_level,
                          score: item.risk_score,
                          priority: item.priority_rank,
                          color: getRiskColor(item.risk_level),
                        };
                        selectRiskLocation(mapLocation);
                        scrollToSection(locationAnalysisRef, "overview");
                      }}
                    >
                      View Analysis →
                    </button>
                  </div>
                ))}
              </div>

              <div className="model-note" style={{ marginTop: "18px" }}>
                Action Priority Index: Transparent decision-support metric combining baseline risk,
                spatial exposure footprint, corridor convergence, bottleneck concentration, and
                scenario stress sensitivity. Inundation is modeled as risk exposure; flooding is not
                guaranteed.
              </div>
            </div>
          </section>

          {/* ================= RISK DISTRIBUTION ================= */}
          <section ref={distributionRef} className="dashboard-card distribution-card">
            <div className="card-header">
              <div>
                <p className="section-eyebrow">CITY-WIDE VIEW</p>

                <h3>Risk Distribution</h3>

                <p>
                  Current distribution across all {stats?.total_locations ?? "the available"}{" "}
                  analysis locations.
                </p>
              </div>
            </div>

            <div className="distribution-grid">
              <div className="distribution-item">
                <span className="distribution-dot red"></span>
                <div>
                  <strong>Very High</strong>
                  <small>
                    {riskDistribution.Very_High ?? riskDistribution["Very High"] ?? 0} locations
                  </small>
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

          {/* ================= METHODOLOGY & DATA HONESTY ================= */}
          <section ref={methodologyRef} className="dashboard-card">
            <div className="card-header">
              <div>
                <p className="section-eyebrow">METHODOLOGY & DATA HONESTY</p>
                <h3>Decision-Support Framework</h3>
                <p>Transparent modeling standards, limits, and municipal guidance.</p>
              </div>
              <div className="demo-badge">Verified Provenance</div>
            </div>

            <div style={{ padding: "0 28px 28px", color: "#94a3b8", fontSize: "12px", lineHeight: "1.7" }}>
              <div className="impact-grid">
                <div className="impact-panel">
                  <span style={{ color: "#60a5fa" }}>MODEL FORMULATION</span>
                  <p style={{ color: "#cbd5e1" }}>
                    Baseline risk synthesizes 5 geospatial factors across 1,013 analysis points:
                    Elevation (25%), Slope (20%), Built-up Area (25%), Rainfall (20%), and Road Density (10%).
                    The Priority Index incorporates spatial impact radius, route exposure, and convergence density.
                  </p>
                </div>

                <div className="impact-panel">
                  <span style={{ color: "#60a5fa" }}>DATA HONESTY PROTOCOL</span>
                  <p style={{ color: "#cbd5e1" }}>
                    FLOWSIGHT does not claim live IoT gauge readings, subterranean pipe condition data,
                    or guaranteed road flooding. Scenarios are labeled as model simulations. Locality
                    names are verified; unverified coordinates default to Location ID.
                  </p>
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