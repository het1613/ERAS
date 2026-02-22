import { useState, useMemo } from "react";
import TranscriptPanel from "./TranscriptPanel";
import MapPanel from "./MapPanel";
import "./Dashboard.css";
import AmbulancePanel, { UnitInfo, VehicleData } from "./AmbulancePanel";
import CasesPanel from "./CasePanel";
import { DispatchInfo } from "./CaseCard";
import { useVehicleUpdates } from "../hooks/useVehicleUpdates";
import { useIncidents } from "../hooks/useIncidents";
import { useDispatchSuggestion } from "../hooks/useDispatchSuggestion";

// Define the two possible views for type safety
type ActiveView = "Ambulances" | "Cases" | "Transcripts";

function vehicleToUnit(v: VehicleData): UnitInfo {
	const statusMap: Record<string, UnitInfo["status"]> = {
		available: "Available",
		dispatched: "Dispatched",
		on_scene: "On-scene",
		returning: "Returning",
		offline: "Returning",
	};
	const label = v.id
		.replace(/[-_]/g, " ")
		.replace(/\b\w/g, (c) => c.toUpperCase());

	return {
		id: label,
		status: statusMap[v.status] ?? "Available",
		crew: "",
		coords: `${v.lat.toFixed(4)}, ${v.lon.toFixed(4)}`,
	};
}

const Dashboard = () => {
	const [activeView, setActiveView] = useState<ActiveView>("Ambulances");
	const [focusedUnit, setFocusedUnit] = useState<UnitInfo | null>(null);
	const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
		null
	);

	const { vehicles, routes, incidentVehicleMap } = useVehicleUpdates();
	const units = vehicles.map(vehicleToUnit);
	const {
		suggestion,
		loading: dispatchLoading,
		findBest,
		accept,
		declineAndReassign,
	} = useDispatchSuggestion();

	// Server-side auto-dispatch handles new incidents now — no client-side callback needed
	const { incidents } = useIncidents();
	const activeIncidents = incidents.filter((i) => i.status !== "resolved");

	// Build a lookup of vehicle statuses by normalized id for dispatch phase inference
	const vehicleStatusById = useMemo(() => {
		const m: Record<string, string> = {};
		for (const v of vehicles) {
			m[v.id] = v.status;
		}
		return m;
	}, [vehicles]);

	// Build dispatch info map for CaseCards
	const dispatchInfoMap = useMemo(() => {
		const map: Record<string, DispatchInfo> = {};

		// Mark incidents that have an active dispatch suggestion
		if (suggestion) {
			map[suggestion.incidentId] = {
				phase: "suggested",
				vehicleId: suggestion.vehicleId,
			};
		}

		// Mark incidents that have a dispatched vehicle (active route)
		for (const [vehicleId] of routes) {
			for (const [incidentId, vId] of Object.entries(incidentVehicleMap)) {
				if (vId === vehicleId && !map[incidentId]) {
					map[incidentId] = {
						phase: "en_route",
						vehicleId,
					};
				}
			}
		}

		// Use vehicle status to determine on_scene phase
		for (const [incidentId, vehicleId] of Object.entries(incidentVehicleMap)) {
			if (map[incidentId]) continue;
			const vStatus = vehicleStatusById[vehicleId];
			if (vStatus === "on_scene") {
				map[incidentId] = { phase: "on_scene", vehicleId };
			}
		}

		// Mark in_progress incidents without routes as "dispatched"
		for (const inc of incidents) {
			if (inc.status === "in_progress" && !map[inc.id]) {
				const vehicleId = incidentVehicleMap[inc.id];
				map[inc.id] = {
					phase: "dispatched",
					vehicleId: vehicleId || undefined,
				};
			}
			if (inc.status === "resolved" && !map[inc.id]) {
				map[inc.id] = { phase: "arrived" };
			}
		}

		return map;
	}, [suggestion, routes, incidentVehicleMap, incidents, vehicleStatusById]);

	const handleViewChange = (view: ActiveView) => {
		setActiveView(view);
	};

	const renderLeftPanel = () => {
		if (activeView === "Ambulances") {
			return (
				<AmbulancePanel
					activeView={activeView}
					handleViewChange={handleViewChange}
					units={units}
					onUnitClick={(unit) => setFocusedUnit(unit)}
				/>
			);
		} else if (activeView === "Cases") {
			return (
				<CasesPanel
					activeView={activeView}
					handleViewChange={handleViewChange}
					incidents={incidents}
					loading={false}
					onDispatch={findBest}
					dispatchLoading={dispatchLoading}
					dispatchInfoMap={dispatchInfoMap}
				/>
			);
		} else {
			return (
				<TranscriptPanel
					selectedSessionId={selectedSessionId}
					onSessionSelect={setSelectedSessionId}
					activeView={activeView}
					handleViewChange={handleViewChange}
				/>
			);
		}
	};

	return (
		<div className="dashboard">
			<div className="dashboard-left">
				{renderLeftPanel()}
			</div>
			<div className="dashboard-right">
				<MapPanel
					units={units}
					focusedUnit={focusedUnit}
					routes={routes}
					incidents={activeIncidents}
					dispatchSuggestion={suggestion}
					onAcceptSuggestion={accept}
					onDeclineSuggestion={declineAndReassign}
				/>
			</div>
		</div>
	);
};

export default Dashboard;
