import { useState } from "react";
// import TranscriptPanel from "./TranscriptPanel"; // Assuming this is not needed now
import MapPanel from "./MapPanel";
import "./Dashboard.css";
import AmbulancePanel, { UnitInfo } from "./AmbulancePanel";
import CasesPanel from "./CasePanel";

// Define the two possible views for type safety
type ActiveView = "Ambulances" | "Cases";

const mockUnits: UnitInfo[] = [
	{
		id: "Ambulance 2001",
		status: "Available",
		crew: "J. Smith, S. Williams",
		coords: "43.4643, -80.5205", // Location A (Start)
	},
	{
		id: "Ambulance 2002",
		status: "Available",
		crew: "A. Doe, B. Johnson",
		coords: "43.4557, -80.4058", // Location B (Airport area)
	},
	{
		id: "Ambulance 2003",
		status: "Returning",
		crew: "C. Lee, D. Brown",
		coords: "43.4700, -80.4500", // Location C (North)
	},
	{
		id: "Ambulance 2004",
		status: "Dispatched",
		crew: "E. Davis, F. Miller",
		coords: "43.4400, -80.4800", // Location D (South)
	},
];

const Dashboard = () => {
	// 1. New state to track the active panel, defaulting to 'Ambulances'
	const [activeView, setActiveView] = useState<ActiveView>("Ambulances");
	const [focusedUnit, setFocusedUnit] = useState<UnitInfo | null>(null);
	const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
		null
	);

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
					units={mockUnits}
					onUnitClick={(unit) => setFocusedUnit(unit)}
				/>
			);
		} else {
			return (
				<CasesPanel
					activeView={activeView}
					handleViewChange={handleViewChange}
				/>
			);
		}
	};

	return (
		<div className="dashboard">
			<div className="dashboard-left">
				{/* Render the selected panel based on state */}
				{renderLeftPanel()}
			</div>
			<div className="dashboard-right">
				<MapPanel units={mockUnits} focusedUnit={focusedUnit} />
			</div>
		</div>
	);
};

export default Dashboard;
