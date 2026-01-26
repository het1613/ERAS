// CasesPanel.tsx
import "./CasePanel.css";
import CaseCard from "./CaseCard"; // <--- IMPORT THE NEW COMPONENT
import { CaseInfo, CasePriority } from "./types"; // <--- IMPORT SHARED TYPES

// --- Mock Data (Stays here because the parent manages the list) ---
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

type PriorityCounts = {
	[key in CasePriority]?: number;
};

// Map priorities to a display color for buttons (Stays here for the top filters)
const priorityColorMap: Record<CasePriority, string> = {
	Purple: "purple-text",
	Red: "red-text",
	Orange: "orange-text",
	Yellow: "yellow-text",
	Green: "green-text",
};

// --- Case Counting Logic ---
const priorityCounts: PriorityCounts = mockCases.reduce((acc, c) => {
	acc[c.priority] = (acc[c.priority] || 0) + 1;
	return acc;
}, {} as PriorityCounts);

export type ActiveView = "Ambulances" | "Cases" | "Transcripts";

interface PanelProps {
	activeView: ActiveView;
	handleViewChange: (view: ActiveView) => void;
}

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
									className={`filter ${priority.toLowerCase()} ${priorityColorMap[priority]
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

				{/* Case List - NOW MUCH CLEANER! */}
				<div className="case-list">
					{mockCases.map((c) => (
						<CaseCard key={c.id} data={c} />
					))}
				</div>
			</div>

			{/* Bottom Navigation */}
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
