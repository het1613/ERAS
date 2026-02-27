export type CasePriority = "Purple" | "Red" | "Orange" | "Yellow" | "Green";

export interface CaseInfo {
  id: string;
  session_id?: string;
  lat: number;
  lon: number;
  location: string;
  type: string;
  priority: CasePriority;
  weight: number;
  status: "open" | "in_progress" | "resolved";
  reported_at: string;
  updated_at: string;
}

export interface DispatchSuggestion {
  suggestionId: string;
  vehicleId: string;
  incidentId: string;
  incident: {
    type: string;
    priority: string;
    location: string;
    lat: number;
    lon: number;
  };
  routePreview: google.maps.LatLngLiteral[];
}

export const PRIORITY_COLORS: Record<CasePriority, string> = {
  Purple: "var(--priority-purple)",
  Red: "var(--priority-red)",
  Orange: "var(--priority-orange)",
  Yellow: "var(--priority-yellow)",
  Green: "var(--priority-green)",
};

export const PRIORITY_BGS: Record<CasePriority, string> = {
  Purple: "var(--priority-purple-bg)",
  Red: "var(--priority-red-bg)",
  Orange: "var(--priority-orange-bg)",
  Yellow: "var(--priority-yellow-bg)",
  Green: "var(--priority-green-bg)",
};

export type ActiveView = "Ambulances" | "Cases";
