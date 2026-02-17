// CaseCard.tsx
import "./CasePanel.css";
import { CaseInfo } from "./types";

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

// --- Props Interface ---
interface CaseCardProps {
	data: CaseInfo;
}

function formatTime(isoString: string | undefined): string {
	if (!isoString) return "";
	const d = new Date(isoString);
	return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// --- The Component ---
export default function CaseCard({ data }: CaseCardProps) {
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
		</div>
	);
}
