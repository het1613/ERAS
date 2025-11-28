import React from "react";
import "./AmbulancePanel.css";

export type UnitStatus = "Available" | "On-scene" | "Returning" | "Dispatched";

interface UnitInfo {
	id: string;
	status: UnitStatus;
	crew: string;
	coords: string;
}

const mockUnits: UnitInfo[] = [
	{
		id: "Ambulance 2001",
		status: "Available",
		crew: "J. Smith, S. Williams",
		coords: "43.4643, -80.4895",
	},
	{
		id: "Ambulance 2002",
		status: "Available",
		crew: "J. Smith, S. Williams",
		coords: "43.4643, -80.4895",
	},
	{
		id: "Ambulance 2003",
		status: "Returning",
		crew: "J. Smith, S. Williams",
		coords: "43.4643, -80.4895",
	},
	{
		id: "Ambulance 2004",
		status: "Dispatched",
		crew: "J. Smith, S. Williams",
		coords: "43.4643, -80.4895",
	},
];

// Define the possible views (make sure this is consistent with Dashboard.tsx)
export type ActiveView = "Ambulances" | "Cases";

// Define the interface for the props the component expects
interface PanelProps {
	activeView: ActiveView;
	// handleViewChange is a function that takes one argument (a string literal: 'Ambulances' or 'Cases')
	// and returns nothing (void).
	handleViewChange: (view: ActiveView) => void;
}

export default function AmbulancePanel({
	activeView,
	handleViewChange,
}: PanelProps): JSX.Element {
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
					{mockUnits.map((u, i) => (
						<div className="unit-card" key={i}>
							<div className="unit-header">
								<span
									className={`status-dot ${u.status
										.toLowerCase()
										.replace("on-scene", "onscene")}`}
								/>
								<span className="unit-id">{u.id}</span>
							</div>

							<div
								className={`unit-status status-${u.status
									.toLowerCase()
									.replace("on-scene", "onscene")}`}
							>
								{u.status}
							</div>

							<div className="unit-row">
								<span className="emoji">👥</span>
								<span>{u.crew}</span>
							</div>

							<div className="unit-row">
								<span className="emoji">📍</span>
								<span>{u.coords}</span>
							</div>
						</div>
					))}
				</div>
			</div>

			{/* Bottom Navigation (Inside both CasePanel.tsx and AmbulancePanel.tsx) */}
			<div className="bottom-nav">
				<button
					className={`nav-item ${
						activeView === "Ambulances" ? "active" : ""
					}`}
					onClick={() => handleViewChange("Ambulances")}
				>
					<span className="emoji">🚑</span> Ambulances
				</button>
				<button
					className={`nav-item ${
						activeView === "Cases" ? "active" : ""
					}`}
					onClick={() => handleViewChange("Cases")}
				>
					<span className="emoji">⚠️</span> Cases
				</button>
			</div>
		</div>
	);
}
