/**
 * FLOWSIGHT Decision-Support API Contracts
 * Exactly matches backend payloads from FastAPI endpoints.
 */

export interface Scenario {
  scenario_id: string;
  name: string;
  type: string;
  description: string;
  rainfall_multiplier: number;
  affected_location_count: number;
  average_risk: number;
  maximum_risk: number;
  risk_distribution: {
    "Very High": number;
    High: number;
    Moderate: number;
    Low: number;
  };
  disclaimer: string;
}

export interface ChangedLocation {
  location_id: number;
  locality: string;
  latitude: number;
  longitude: number;
  baseline_risk_score: number;
  scenario_risk_score: number;
  risk_delta: number;
  baseline_risk_level: string;
  scenario_risk_level: string;
}

export interface ScenarioComparison {
  scenario_id: string;
  name: string;
  type: string;
  baseline_average_risk: number;
  scenario_average_risk: number;
  baseline_maximum_risk: number;
  scenario_maximum_risk: number;
  average_risk_delta: number;
  maximum_risk_delta: number;
  locations_whose_risk_level_increased: number;
  locations_whose_risk_level_decreased: number;
  baseline_risk_distribution: Record<string, number>;
  scenario_risk_distribution: Record<string, number>;
  newly_elevated_hotspots_count: number;
  newly_elevated_hotspots: ChangedLocation[];
  top_changed_locations: ChangedLocation[];
  disclaimer: string;
}

export interface BottleneckLocation {
  location_id: number;
  locality: string;
  latitude: number;
  longitude: number;
  risk_score: number;
  risk_level: string;
  elevation: number;
  slope: number;
  built_up: number;
  road_density: number;
}

export interface Bottleneck {
  bottleneck_id: string;
  name: string;
  locality: string;
  center_latitude: number;
  center_longitude: number;
  radius_km: number;
  number_of_high_risk_locations: number;
  average_risk: number;
  maximum_risk: number;
  nearby_route_count: number;
  affected_area_estimate: number;
  bottleneck_score: number;
  risk_level: string;
  priority: number;
  contributing_locations?: BottleneckLocation[];
  nearby_routes?: Array<{
    corridor_id: string;
    name: string;
    average_risk_score: number;
    exposure_level: string;
    distance_to_center_km: number;
  }>;
  polygon_coordinates?: number[][];
  explanation?: string;
  recommended_action?: string;
  disclaimer: string;
}

export interface PriorityLocation {
  priority_index: number;
  priority_rank: number;
  location_id: number;
  locality: string;
  latitude: number;
  longitude: number;
  risk_score: number;
  risk_level: string;
  affected_area: number;
  exposure_radius: number;
  exposed_route_count: number;
  bottleneck_score: number;
  scenario_sensitivity: number;
  recommended_action: string;
  explanation: string;
  component_scores?: {
    risk_score_component: number;
    exposure_radius_component: number;
    affected_area_component: number;
    route_exposure_component: number;
    bottleneck_component: number;
    scenario_sensitivity_component: number;
  };
  weights?: Record<string, number>;
  disclaimer: string;
}
