import { useState } from "react";
import TranscriptPanel from "./TranscriptPanel";
import MapPanel from "./MapPanel";
import "./Dashboard.css";
import AmbulancePanel, { UnitInfo, VehicleData } from "./AmbulancePanel";
import CasesPanel from "./CasePanel";
import { useVehicleUpdates } from "../hooks/useVehicleUpdates";

// Define the two possible views for type safety
type ActiveView = "Ambulances" | "Cases" | "Transcripts";

function vehicleToUnit(v: VehicleData): UnitInfo {
	const statusMap: Record<string, UnitInfo["status"]> = {
		available: "Available",
		dispatched: "Dispatched",
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
	// 1. New state to track the active panel, defaulting to 'Ambulances'
	const [activeView, setActiveView] = useState<ActiveView>("Ambulances");
	const [focusedUnit, setFocusedUnit] = useState<UnitInfo | null>(null);
	const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
		null
	);

	const { vehicles } = useVehicleUpdates();
	const units = vehicles.map(vehicleToUnit);

	// 2. Function to pass down to the navigation buttons
	const handleViewChange = (view: ActiveView) => {
		setActiveView(view);
	};

	// 3. Conditional Rendering logic
	const renderLeftPanel = () => {
		if (activeView === "Ambulances") {
			return (
				<AmbulancePanel
					// 1. Pass the missing props here
					activeView={activeView}
					handleViewChange={handleViewChange}
					// 2. Keep your existing new props
					units={units}
					onUnitClick={(unit) => setFocusedUnit(unit)}
				/>
			);
		} else if (activeView === "Cases") {
			return (
				<CasesPanel
					activeView={activeView}
					handleViewChange={handleViewChange}
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
				{/*
                    If the navigation is inside the panels, we need to ensure TranscriptPanel also has it.
                    Or we should move navigation here.
                    Let's see where the navigation is.
                */}
				{/* Render the selected panel based on state */}
				{renderLeftPanel()}
			</div>
			<div className="dashboard-right">
				<MapPanel units={units} focusedUnit={focusedUnit} />
			</div>
		</div>
	);
};

export default Dashboard;
