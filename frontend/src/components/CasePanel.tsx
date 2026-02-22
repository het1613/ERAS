// CasesPanel.tsx
import "./CasePanel.css";
import CaseCard, { DispatchInfo } from "./CaseCard";
import { CaseInfo, CasePriority } from "./types";

type PriorityCounts = {
	[key in CasePriority]?: number;
};

const priorityColorMap: Record<CasePriority, string> = {
	Purple: "purple-text",
	Red: "red-text",
	Orange: "orange-text",
	Yellow: "yellow-text",
	Green: "green-text",
};

export type ActiveView = "Ambulances" | "Cases" | "Transcripts";

interface PanelProps {
	activeView: ActiveView;
	handleViewChange: (view: ActiveView) => void;
	incidents: CaseInfo[];
	loading?: boolean;
	onDispatch?: (incidentId: string) => void;
	dispatchLoading?: boolean;
	dispatchInfoMap?: Record<string, DispatchInfo>;
}

export default function CasesPanel({
	activeView,
	handleViewChange,
	incidents,
	loading = false,
	onDispatch,
	dispatchLoading,
	dispatchInfoMap = {},
}: PanelProps): JSX.Element {

	const priorityCounts: PriorityCounts = incidents.reduce((acc, c) => {
		acc[c.priority] = (acc[c.priority] || 0) + 1;
		return acc;
	}, {} as PriorityCounts);

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

				{/* Case List */}
				<div className="case-list">
					{loading ? (
						<p>Loading incidents...</p>
					) : incidents.length === 0 ? (
						<p>No incidents reported.</p>
					) : (
						incidents.map((c) => (
							<CaseCard
								key={c.id}
								data={c}
								onDispatch={onDispatch}
								dispatchLoading={dispatchLoading}
								dispatchInfo={dispatchInfoMap[c.id]}
							/>
						))
					)}
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
