import { useState, useMemo } from "react";
import { Truck, AlertTriangle } from "lucide-react";
import MapPanel from "./MapPanel";
import AmbulancePanel, { UnitInfo, VehicleData } from "./AmbulancePanel";
import CasesPanel from "./CasePanel";
import { DispatchInfo } from "./CaseCard";
import { ActiveView } from "./types";
import { useVehicleUpdates } from "../hooks/useVehicleUpdates";
import { useIncidents } from "../hooks/useIncidents";
import { useDispatchSuggestion } from "../hooks/useDispatchSuggestion";
import "./Dashboard.css";

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
	const [activeView, setActiveView] = useState<ActiveView>("Cases");
	const [focusedUnit, setFocusedUnit] = useState<UnitInfo | null>(null);

	const { vehicles, routes, incidentVehicleMap } = useVehicleUpdates();
	const units = vehicles.map(vehicleToUnit);
	const {
		suggestion,
		loading: dispatchLoading,
		findBest,
		accept,
		declineAndReassign,
	} = useDispatchSuggestion();

	const { incidents } = useIncidents();

	const activeIncidents = useMemo(
		() => incidents.filter((i) => i.status !== "resolved"),
		[incidents],
	);

	const vehicleStatusById = useMemo(() => {
		const m: Record<string, string> = {};
		for (const v of vehicles) m[v.id] = v.status;
		return m;
	}, [vehicles]);

	const dispatchInfoMap = useMemo(() => {
		const map: Record<string, DispatchInfo> = {};

		if (suggestion) {
			map[suggestion.incidentId] = { phase: "suggested", vehicleId: suggestion.vehicleId };
		}

		for (const [vehicleId] of routes) {
			for (const [incidentId, vId] of Object.entries(incidentVehicleMap)) {
				if (vId === vehicleId && !map[incidentId]) {
					map[incidentId] = { phase: "en_route", vehicleId };
				}
			}
		}

		for (const [incidentId, vehicleId] of Object.entries(incidentVehicleMap)) {
			if (map[incidentId]) continue;
			const vStatus = vehicleStatusById[vehicleId];
			if (vStatus === "on_scene") {
				map[incidentId] = { phase: "on_scene", vehicleId };
			}
		}

		for (const inc of incidents) {
			if (inc.status === "in_progress" && !map[inc.id]) {
				const vehicleId = incidentVehicleMap[inc.id];
				map[inc.id] = { phase: "dispatched", vehicleId: vehicleId || undefined };
			}
			if (inc.status === "resolved" && !map[inc.id]) {
				map[inc.id] = { phase: "arrived" };
			}
		}

		return map;
	}, [suggestion, routes, incidentVehicleMap, incidents, vehicleStatusById]);

	// Build assignment context for ambulance cards
	const assignmentMap = useMemo(() => {
		const m: Record<string, { incidentType: string; location: string }> = {};
		for (const [incidentId, vehicleId] of Object.entries(incidentVehicleMap)) {
			const inc = incidents.find(i => i.id === incidentId);
			if (inc && inc.status !== "resolved") {
				m[vehicleId] = { incidentType: inc.type || "Incident", location: inc.location || "Unknown" };
			}
		}
		return m;
	}, [incidentVehicleMap, incidents]);

	const activeCaseCount = incidents.filter(i => i.status !== "resolved").length;

	return (
		<div className="dash">
			<div className="dash-left">
				{/* Tab Bar */}
				<div className="dash-tabs">
					<button
						className={`dash-tab ${activeView === "Cases" ? "active" : ""}`}
						onClick={() => setActiveView("Cases")}
					>
						<AlertTriangle size={14} />
						<span>Cases</span>
						{activeCaseCount > 0 && <span className="dash-tab-count">{activeCaseCount}</span>}
					</button>
					<button
						className={`dash-tab ${activeView === "Ambulances" ? "active" : ""}`}
						onClick={() => setActiveView("Ambulances")}
					>
						<Truck size={14} />
						<span>Ambulances</span>
						<span className="dash-tab-count">{units.length}</span>
					</button>
				</div>

				{/* Panel Content */}
				<div className="dash-panel-content">
					{activeView === "Cases" ? (
						<CasesPanel
							activeView={activeView}
							handleViewChange={setActiveView}
							incidents={incidents}
							loading={false}
							onDispatch={findBest}
							dispatchLoading={dispatchLoading}
							dispatchInfoMap={dispatchInfoMap}
						/>
					) : (
						<AmbulancePanel
							activeView={activeView}
							handleViewChange={setActiveView}
							units={units}
							onUnitClick={(unit) => setFocusedUnit(unit)}
							assignmentMap={assignmentMap}
						/>
					)}
				</div>
			</div>

			<div className="dash-right">
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
