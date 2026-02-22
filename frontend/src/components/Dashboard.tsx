import { useState } from "react";
import MapPanel from "./MapPanel";
import "./Dashboard.css";
import AmbulancePanel, { UnitInfo } from "./AmbulancePanel";
import CasesPanel from "./CasePanel";
import { CaseInfo } from "./types";

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

const mockCases: CaseInfo[] = [
	{
		id: "inc-001",
		priority: "Red",
		type: "Chest Pain",
		location: "200 University Ave W, Waterloo",
		reportedTime: "17:35",
		lat: 43.4643,
		lng: -80.5204,
	},
	{
		id: "inc-002",
		priority: "Purple",
		type: "Motor Vehicle Collision",
		location: "85 King St S, Waterloo",
		reportedTime: "17:30",
		lat: 43.4516,
		lng: -80.4925,
	},
	{
		id: "inc-003",
		priority: "Orange",
		type: "Breathing Problems",
		location: "435 Erb St W, Waterloo",
		reportedTime: "17:25",
		lat: 43.4340,
		lng: -80.5224,
	},
	{
		id: "inc-004",
		priority: "Yellow",
		type: "Falls",
		location: "330 Phillip St, Waterloo",
		reportedTime: "17:20",
		lat: 43.4761,
		lng: -80.5283,
	},
	{
		id: "inc-005",
		priority: "Red",
		type: "Unconscious/Fainting",
		location: "295 King St E, Kitchener",
		reportedTime: "17:15",
		lat: 43.4506,
		lng: -80.4830,
	},
	{
		id: "inc-006",
		priority: "Purple",
		type: "Stroke/CVA",
		location: "750 Ottawa St S, Kitchener",
		reportedTime: "17:10",
		lat: 43.4280,
		lng: -80.4680,
	},
	{
		id: "inc-007",
		priority: "Orange",
		type: "Allergic Reaction",
		location: "1187 Fischer-Hallman Rd, Cambridge",
		reportedTime: "17:05",
		lat: 43.3945,
		lng: -80.3982,
	},
	{
		id: "inc-008",
		priority: "Yellow",
		type: "Seizures",
		location: "100 Columbia St W, Waterloo",
		reportedTime: "17:00",
		lat: 43.4488,
		lng: -80.5485,
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
				<MapPanel units={mockUnits} focusedUnit={focusedUnit} cases={mockCases} />
			</div>
		</div>
	);
};

export default Dashboard;
