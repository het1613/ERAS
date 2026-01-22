import React from "react";
// You should create an AmbulanceCard.css file OR reuse AmbulancePanel.css for card-specific styles.
// import "./AmbulanceCard.css";
import AmbulanceIcon from "../assets/ambulance.svg?react";

// --- Type Definitions (Copy these from AmbulancePanel.tsx) ---
export type UnitStatus = "Available" | "On-scene" | "Returning" | "Dispatched";

interface UnitInfo {
	id: string;
	status: UnitStatus;
	crew: string;
	coords: string;
}

// Define the component's props
interface AmbulanceCardProps {
	unitData: UnitInfo;
}

const AmbulanceCard: React.FC<AmbulanceCardProps> = ({ unitData }) => {
	// Determine the status class, similar to how it was done in AmbulancePanel.tsx
	const statusClass = unitData.status
		.toLowerCase()
		.replace("on-scene", "onscene");

	return (
		<div className="unit-card">
			<div className="warning-icon">
				<AmbulanceIcon className={`icon_css icon_css-${statusClass}`} />
			</div>

			{/* <div className="warning-icon">
				<span
					className="material-icons icon_css"
					style={{ color: getPriorityColor(data.priority) }}
				>
					warning
				</span>
			</div> */}

			<div className="unit-header">
				<span className={`status-dot ${statusClass}`} />
				<span className="unit-id">{unitData.id}</span>
			</div>

			<div className={`unit-status status-${statusClass}`}>
				{unitData.status}
			</div>

			<div className="unit-row">
				<span className="emoji">👥</span>
				<span>{unitData.crew}</span>
			</div>

			<div className="unit-row">
				<span className="emoji">📍</span>
				<span>{unitData.coords}</span>
			</div>
		</div>
	);
};

export default AmbulanceCard;
