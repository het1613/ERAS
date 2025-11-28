import React from "react";
import "./CasePanel.css";

// --- Type Definitions ---
export type CasePriority = "Purple" | "Red" | "Orange" | "Yellow" | "Green";

interface CaseInfo {
	id: string;
	priority: CasePriority;
	type: string;
	location: string;
	reportedTime: string;
}

type PriorityCounts = {
	[key in CasePriority]?: number;
};

// Map priorities to a display color for buttons
const priorityColorMap: Record<CasePriority, string> = {
	Purple: "purple-text",
	Red: "red-text",
	Orange: "orange-text",
	Yellow: "yellow-text",
	Green: "green-text",
};

// --- Mock Data ---
const mockCases: CaseInfo[] = [
	{
		id: "Case-001",
		priority: "Purple",
		type: "Cardiac Arrest",
		location: "234 Columbia Street",
		reportedTime: "17:35",
	},
	{
		id: "Case-002",
		priority: "Purple",
		type: "Cardiac Arrest",
		location: "234 Columbia Street",
		reportedTime: "17:35",
	},
	{
		id: "Case-003",
		priority: "Red",
		type: "Cardiac Arrest",
		location: "234 Columbia Street",
		reportedTime: "17:35",
	},
	{
		id: "Case-004",
		priority: "Orange",
		type: "Broken Hand",
		location: "994 Columbia Street",
		reportedTime: "17:30",
	},
	{
		id: "Case-005",
		priority: "Yellow",
		type: "Flu Symptoms",
		location: "123 Main Street",
		reportedTime: "17:20",
	},
	{
		id: "Case-006",
		priority: "Green",
		type: "Minor Cuts",
		location: "456 Side Road",
		reportedTime: "17:15",
	},
];

// --- Case Counting Logic ---
const priorityCounts: PriorityCounts = mockCases.reduce((acc, c) => {
	acc[c.priority] = (acc[c.priority] || 0) + 1;
	return acc;
}, {} as PriorityCounts);

// --- Material Design Icon Placeholder for WARNING ---
const MDI_ICON_ALERT = <span className="mdi-icon mdi-alert">warning</span>;

// Define the possible views (make sure this is consistent with Dashboard.tsx)
export type ActiveView = "Ambulances" | "Cases";

// Define the interface for the props the component expects
interface PanelProps {
	activeView: ActiveView;
	// handleViewChange is a function that takes one argument (a string literal: 'Ambulances' or 'Cases')
	// and returns nothing (void).
	handleViewChange: (view: ActiveView) => void;
}

// --- Component Definition ---
export default function CasesPanel({
	activeView,
	handleViewChange,
}: PanelProps): JSX.Element {
	return (
		<div className="dispatch-panel cases-panel">
			{/* Top Bar with Title */}
			<div className="top-nav">
				<h2 className="panel-title">
					<span className="emoji">🚑</span> Emergency Dispatch
				</h2>

				{/* Status Filter Buttons */}
				<div className="status-filters">
					{(Object.keys(priorityCounts) as CasePriority[]).map(
						(priority) => {
							const count = priorityCounts[priority] || 0;
							return (
								<button
									key={priority}
									className={`filter ${priority.toLowerCase()} ${
										priorityColorMap[priority]
									}`}
								>
									{count} {priority}
								</button>
							);
						}
					)}
					<button className="filter all">All</button>
				</div>
			</div>

			<div className="active-cases">
				<h3 className="section-title">Active Cases</h3>

				{/* Case List */}
				<div className="case-list">
					{mockCases.map((c, i) => (
						<div className="case-card" key={i}>
							{/* 1. WARNING ICON (Absolute Positioned - Direct child of case-card) */}
							<div className="warning-icon">
								<span
									className={`priority-icon priority-${c.priority.toLowerCase()}`}
								>
									{MDI_ICON_ALERT}
								</span>
							</div>

							{/* 2. HEADER VISUALS (Title + Bar/Square) */}
							<div className="case-header-visuals">
								{/* The Title (e.g., Cardiac Arrest) */}
								<span className="case-type">{c.type}</span>

								{/* The Purple Bar and Purple Square */}
								<div className="priority-bars-container">
									<div
										className={`priority-bar priority-bar-${c.priority.toLowerCase()}`}
									/>
									<div
										className={`priority-square priority-square-${c.priority.toLowerCase()}`}
									/>
								</div>
							</div>

							{/* 3. CASE DETAILS (Location and Time) */}
							<div className="case-details-content">
								{/* Location (Emoji) */}
								<div className="case-row">
									<span className="emoji">📍</span>
									<span>{c.location}</span>
								</div>

								{/* Reported Time (Emoji) */}
								<div className="case-row">
									<span className="emoji">🕒</span>
									<span>Reported at {c.reportedTime}</span>
								</div>
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
