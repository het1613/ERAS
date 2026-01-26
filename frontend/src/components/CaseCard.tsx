// CaseCard.tsx
import "./CasePanel.css"; // Keep the CSS import so styles work
import { CaseInfo } from "./types"; // Import the shared type

// --- Helper for Colors (Moved here because only the card needs it) ---
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

// --- Props Interface ---
interface CaseCardProps {
	data: CaseInfo;
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

			{/* 3. CASE DETAILS */}
			<div className="case-details-content">
				<div className="case-row">
					<span className="emoji">📍</span>
					<span>{data.location}</span>
				</div>
				<div className="case-row">
					<span className="emoji">🕒</span>
					<span>Reported at {data.reportedTime}</span>
				</div>
			</div>
		</div>
	);
}
