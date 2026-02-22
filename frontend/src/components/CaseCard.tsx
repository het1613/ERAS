// CaseCard.tsx
import "./CasePanel.css";
import { CaseInfo } from "./types";

export type DispatchPhase =
	| "finding"       // Server is searching for optimal ambulance
	| "suggested"     // Dispatch suggestion shown on map, waiting for dispatcher
	| "dispatched"    // Dispatcher accepted, ambulance dispatched
	| "en_route"      // Ambulance following route
	| "on_scene"      // Ambulance on scene
	| "arrived"       // Ambulance arrived / incident resolved
	| null;           // No active dispatch

export interface DispatchInfo {
	phase: DispatchPhase;
	vehicleId?: string;
}

// --- Helper for Colors ---
const getPriorityColor = (p: string) => {
	switch (p) {
		case "Purple":
			return "#884dff";
		case "Red":
			return "#d6455d";
		case "Orange":
			return "#e29a00";
		case "Yellow":
			return "#d4a700";
		case "Green":
			return "#2e994e";
		default:
			return "#000";
	}
};

const statusLabel: Record<string, string> = {
	open: "Open",
	in_progress: "In Progress",
	resolved: "Resolved",
};

const DISPATCH_PHASE_CONFIG: Record<string, { label: string; className: string }> = {
	finding:    { label: "Finding Ambulance...", className: "dispatch-phase-finding" },
	suggested:  { label: "Ambulance Suggested",  className: "dispatch-phase-suggested" },
	dispatched: { label: "Dispatched",           className: "dispatch-phase-dispatched" },
	en_route:   { label: "En Route",             className: "dispatch-phase-enroute" },
	on_scene:   { label: "On Scene",             className: "dispatch-phase-onscene" },
	arrived:    { label: "Arrived",              className: "dispatch-phase-arrived" },
};

// --- Props Interface ---
interface CaseCardProps {
	data: CaseInfo;
	onDispatch?: (incidentId: string) => void;
	dispatchLoading?: boolean;
	dispatchInfo?: DispatchInfo;
}

function formatTime(isoString: string | undefined): string {
	if (!isoString) return "";
	const d = new Date(isoString);
	return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatVehicleLabel(vehicleId: string): string {
	return vehicleId
		.replace(/[-_]/g, " ")
		.replace(/\b\w/g, (c) => c.toUpperCase());
}

// --- The Component ---
export default function CaseCard({ data, onDispatch, dispatchLoading, dispatchInfo }: CaseCardProps) {
	const phase = dispatchInfo?.phase;
	const phaseConfig = phase ? DISPATCH_PHASE_CONFIG[phase] : null;

	return (
		<div className="case-card">
			{/* 1. WARNING ICON */}
			<div className="warning-icon">
				<span
					className="material-icons icon_css"
					style={{ color: getPriorityColor(data.priority) }}
				>
					warning
				</span>
			</div>

			{/* 2. HEADER VISUALS */}
			<div className="case-header-visuals">
				<span className={`status-dot ${data.priority}`} />
				<span className="case-type">{data.type}</span>
			</div>

			<div className={`case-status status-${data.priority}`}>
				{data.priority}
			</div>

			{/* Status badge */}
			<div className={`case-status-badge status-badge-${data.status}`}>
				{statusLabel[data.status] || data.status}
			</div>

			{/* 3. CASE DETAILS */}
			<div className="case-details-content">
				<div className="case-row">
					<span className="emoji">📍</span>
					<span>{data.location}</span>
				</div>
				<div className="case-row">
					<span className="emoji">🕒</span>
					<span>Reported at {formatTime(data.reported_at)}</span>
				</div>
			</div>

			{/* 4. DISPATCH STATUS */}
			{phaseConfig && (
				<div className={`dispatch-phase-indicator ${phaseConfig.className}`}>
					<span className="dispatch-phase-label">{phaseConfig.label}</span>
					{dispatchInfo?.vehicleId && (
						<span className="dispatch-vehicle-label">
							{formatVehicleLabel(dispatchInfo.vehicleId)}
						</span>
					)}
				</div>
			)}

			{/* 5. DISPATCH BUTTON (only when open and no active dispatch) */}
			{data.status === "open" && !phase && onDispatch && (
				<button
					className="dispatch-btn"
					disabled={dispatchLoading}
					onClick={() => onDispatch(data.id)}
				>
					{dispatchLoading ? "Finding..." : "Dispatch"}
				</button>
			)}
		</div>
	);
}
