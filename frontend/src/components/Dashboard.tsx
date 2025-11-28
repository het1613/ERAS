import { useState } from "react";
// import TranscriptPanel from "./TranscriptPanel"; // Assuming this is not needed now
import MapPanel from "./MapPanel";
import "./Dashboard.css";
import AmbulancePanel from "./AmbulancePanel";
import CasesPanel from "./CasePanel";

// Define the two possible views for type safety
type ActiveView = "Ambulances" | "Cases";

const Dashboard = () => {
	// 1. New state to track the active panel, defaulting to 'Ambulances'
	const [activeView, setActiveView] = useState<ActiveView>("Ambulances");

	const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
		null
	);

	// 2. Function to pass down to the navigation buttons
	const handleViewChange = (view: ActiveView) => {
		setActiveView(view);
	};

	// 3. Conditional Rendering logic
	const renderLeftPanel = () => {
		// Both panels are passed the current activeView and the handler function.
		if (activeView === "Ambulances") {
			return (
				<AmbulancePanel
					activeView={activeView}
					handleViewChange={handleViewChange}
				/>
			);
		} else {
			// activeView === 'Cases'
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
				<MapPanel sessionId={selectedSessionId} />
			</div>
		</div>
	);
};

export default Dashboard;
