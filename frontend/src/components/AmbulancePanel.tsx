import "./AmbulancePanel.css";
import AmbulanceCard from "./AmbulanceCard";

export type UnitStatus = "Available" | "On-scene" | "Returning" | "Dispatched";

export interface UnitInfo {
	id: string;
	status: UnitStatus;
	crew: string;
	coords: string;
}

// Define the possible views (make sure this is consistent with Dashboard.tsx)
export type ActiveView = "Ambulances" | "Cases" | "Transcripts";

// Define the interface for the props the component expects
interface PanelProps {
	activeView: ActiveView;
	handleViewChange: (view: ActiveView) => void;
	// NEW PROPS
	units: UnitInfo[];
	onUnitClick: (unit: UnitInfo) => void;
}

export default function AmbulancePanel({
	activeView,
	handleViewChange,
	units, // Receive units
	onUnitClick, // Receive click handler
}: PanelProps) {
	return (
		<div className="dispatch-panel">
			{/* Top Bar*/}
			<div className="top-nav">
				<h2 className="panel-title">Emergency Dispatch</h2>

				{/* Status Filter Buttons */}
				<div className="status-filters">
					<button className="filter available">2 Available</button>
					<button className="filter dispatched">1 Dispatched</button>
					<button className="filter onscene">2 On-scene</button>
					<button className="filter returning">1 Returning</button>
					<button className="filter all">All</button>
				</div>
			</div>

			<div className="active-units">
				<h3 className="section-title">Active Units</h3>

				{/* Unit List */}
				<div className="unit-list">
					{units.map((u) => (
						// Wrap the card in a div to handle the click
						<div
							key={u.id}
							onClick={() => onUnitClick(u)}
							style={{ cursor: "pointer" }}
						>
							<AmbulanceCard unitData={u} />
						</div>
					))}
				</div>
			</div>

			{/* Bottom Navigation (Inside both CasePanel.tsx and AmbulancePanel.tsx) */}
			<div className="bottom-nav">
				<button
					className={`nav-item ${activeView === "Ambulances" ? "active" : ""
						}`}
					onClick={() => handleViewChange("Ambulances")}
				>
					<span className="emoji">🚑</span> Ambulances
				</button>
				<button
					className={`nav-item ${activeView === "Cases" ? "active" : ""
						}`}
					onClick={() => handleViewChange("Cases")}
				>
					<span className="emoji">⚠️</span> Cases
				</button>
				<button
					className={`nav-item ${activeView === "Transcripts" ? "active" : ""
						}`}
					onClick={() => handleViewChange("Transcripts")}
				>
					<span className="emoji">📝</span> Transcripts
				</button>
			</div>
		</div>
	);
}
