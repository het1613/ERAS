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
		transporting: "Dispatched",
		at_hospital: "On-scene",
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

	// Only show call-taker-originated incidents in the cases tab
	const callTakerIncidents = useMemo(
		() => incidents.filter((i) => i.source === "call_taker"),
		[incidents],
	);

	const activeIncidents = useMemo(
		() => incidents.filter((i) => i.status !== "resolved"),
		[incidents],
	);

	const vehicleStatusById = useMemo(() => {
		const m: Record<string, string> = {};
		for (const v of vehicles) m[v.id] = v.status;
		return m;
	}, [vehicles]);

	// Build dispatch info from persisted incident status (status is now granular enough)
	const dispatchInfoMap = useMemo(() => {
		const map: Record<string, DispatchInfo> = {};

		// Active dispatch suggestion (highest priority)
		if (suggestion) {
			map[suggestion.incidentId] = { phase: "suggested", vehicleId: suggestion.vehicleId };
		}

		for (const inc of incidents) {
			if (map[inc.id]) continue;

			const vehicleId = inc.assigned_vehicle_id || incidentVehicleMap[inc.id];
			const vStatus = vehicleId ? vehicleStatusById[vehicleId] : undefined;

			switch (inc.status) {
				case "dispatched": {
					const hasRoute = vehicleId && routes.some(([vid]) => vid === vehicleId);
					map[inc.id] = { phase: hasRoute ? "en_route" : "dispatched", vehicleId };
					break;
				}
				case "en_route":
					map[inc.id] = { phase: "en_route", vehicleId };
					break;
				case "on_scene":
					map[inc.id] = { phase: "on_scene", vehicleId };
					break;
				case "transporting":
					map[inc.id] = { phase: "transporting", vehicleId };
					break;
				case "at_hospital":
					map[inc.id] = { phase: "at_hospital", vehicleId };
					break;
				case "resolved":
					map[inc.id] = { phase: "resolved" };
					break;
			}
		}

		return map;
	}, [suggestion, incidents, routes, incidentVehicleMap, vehicleStatusById]);

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

	const activeCaseCount = callTakerIncidents.filter(i => i.status !== "resolved").length;

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
							incidents={callTakerIncidents}
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
