/**
 * FLOWSIGHT API Client Service
 * Strictly interfaces with the FastAPI backend on port 8000.
 * Preserves all existing endpoints and adds decision-support API contracts.
 */

export const API_BASE_URL = "http://127.0.0.1:8000";

async function fetchJson(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, options);
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error (${response.status} ${response.statusText}): ${errorText}`);
  }
  return response.json();
}

// =====================================================================
// EXISTING ENDPOINTS
// =====================================================================

export async function getStats() {
  return fetchJson("/api/stats");
}

export async function getTopRisk(limit = 10) {
  return fetchJson(`/api/top-risk?limit=${limit}`);
}

export async function getAllLocations() {
  return fetchJson("/api/locations");
}

export async function getLocationById(locationId) {
  return fetchJson(`/api/locations/${locationId}`);
}

export async function getLocationExplanation(locationId) {
  return fetchJson(`/api/locations/${locationId}/explanation`);
}

export async function getLocationImpact(locationId) {
  return fetchJson(`/api/locations/${locationId}/impact`);
}

export async function getLocalities() {
  return fetchJson("/api/localities");
}

export async function getImpactSummary() {
  return fetchJson("/api/impact/summary");
}

export async function getRankedRoutes(limit = 10) {
  return fetchJson(`/api/impact/routes?limit=${limit}`);
}

// =====================================================================
// FEATURE 1: SCENARIOS & EVENT REPLAY
// =====================================================================

export async function getScenarios() {
  return fetchJson("/api/scenarios");
}

export async function getScenario(scenarioId) {
  return fetchJson(`/api/scenarios/${encodeURIComponent(scenarioId)}`);
}

export async function compareScenario(scenarioId) {
  return fetchJson(`/api/scenarios/${encodeURIComponent(scenarioId)}/compare`);
}

// =====================================================================
// FEATURE 2: POTENTIAL DRAINAGE BOTTLENECKS
// =====================================================================

export async function getBottlenecks({ min_risk = 60.0, radius = 1.5, limit = 10 } = {}) {
  const query = new URLSearchParams({
    min_risk: String(min_risk),
    radius: String(radius),
    limit: String(limit),
  });
  return fetchJson(`/api/impact/bottlenecks?${query.toString()}`);
}

export async function getBottleneck(bottleneckId) {
  return fetchJson(`/api/impact/bottlenecks/${encodeURIComponent(bottleneckId)}`);
}

// =====================================================================
// FEATURE 3: ACTION PRIORITY
// =====================================================================

export async function getPriorityLocations({ limit = 10, scenario_id = null } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (scenario_id) {
    query.set("scenario_id", scenario_id);
  }
  return fetchJson(`/api/priority?${query.toString()}`);
}

export async function getPriorityLocation(locationId, scenarioId = null) {
  const query = scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : "";
  return fetchJson(`/api/priority/${locationId}${query}`);
}
