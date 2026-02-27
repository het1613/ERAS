import { useMemo } from "react";
import { Truck, Navigation, MapPin } from "lucide-react";
import Badge from "./ui/Badge";
import EmptyState from "./ui/EmptyState";
import { ActiveView } from "./types";
import "./AmbulancePanel.css";

export type UnitStatus = "Available" | "On-scene" | "Returning" | "Dispatched";

export interface UnitInfo {
	id: string;
	status: UnitStatus;
	crew: string;
	coords: string;
}

export interface VehicleData {
	id: string;
	lat: number;
	lon: number;
	status: string;
	vehicle_type: string;
}

const STATUS_CONFIG: Record<UnitStatus, { color: string; bg: string }> = {
	Available: { color: "var(--status-available)", bg: "var(--status-available-bg)" },
	Dispatched: { color: "var(--status-dispatched)", bg: "var(--status-dispatched-bg)" },
	"On-scene": { color: "var(--status-onscene)", bg: "var(--status-onscene-bg)" },
	Returning: { color: "var(--status-returning)", bg: "var(--status-returning-bg)" },
};

const STATUS_SORT_ORDER: Record<UnitStatus, number> = {
	Dispatched: 0,
	"On-scene": 1,
	Available: 2,
	Returning: 3,
};

interface PanelProps {
	activeView: ActiveView;
	handleViewChange: (view: ActiveView) => void;
	units: UnitInfo[];
	onUnitClick: (unit: UnitInfo) => void;
	assignmentMap?: Record<string, { incidentType: string; location: string }>;
}

export default function AmbulancePanel({
	units,
	onUnitClick,
	assignmentMap = {},
}: PanelProps) {
	const sortedUnits = useMemo(() => {
		return [...units].sort((a, b) => {
			const aOrder = STATUS_SORT_ORDER[a.status] ?? 9;
			const bOrder = STATUS_SORT_ORDER[b.status] ?? 9;
			return aOrder - bOrder;
		});
	}, [units]);

	const statusCounts = useMemo(() => {
		const counts: Partial<Record<UnitStatus, number>> = {};
		for (const u of units) counts[u.status] = (counts[u.status] || 0) + 1;
		return counts;
	}, [units]);

	return (
		<div className="dp-section">
			{/* Status summary */}
			<div className="dp-priority-summary">
				{(["Dispatched", "On-scene", "Available", "Returning"] as UnitStatus[]).map(s => {
					const count = statusCounts[s];
					if (!count) return null;
					const cfg = STATUS_CONFIG[s];
					return (
						<Badge key={s} variant="priority" size="sm" dot color={cfg.color} bg={cfg.bg}>
							{count} {s}
						</Badge>
					);
				})}
			</div>

			{/* Unit List */}
			<div className="dp-case-list">
				{sortedUnits.length === 0 ? (
					<EmptyState title="No units available" />
				) : (
					sortedUnits.map(u => {
						const cfg = STATUS_CONFIG[u.status];
						const assignment = assignmentMap[u.id.toLowerCase().replace(/\s+/g, "-")];

						return (
							<button
								key={u.id}
								className="amb-card"
								style={{ borderLeftColor: cfg.color }}
								onClick={() => onUnitClick(u)}
							>
							<div className="amb-card-top">
								<Truck size={14} style={{ color: cfg.color }} />
								<span className="amb-card-name">{u.id}</span>
								<Badge variant="priority" size="sm" dot color={cfg.color} bg={cfg.bg}>
									{u.status}
								</Badge>
							</div>
							<div className="amb-card-location">
								<MapPin size={11} />
								<span className="amb-card-coords">{u.coords}</span>
							</div>
							{assignment && (
								<div className="amb-card-assignment">
									<Navigation size={11} />
									<span>{assignment.incidentType} @ {assignment.location}</span>
								</div>
							)}
							</button>
						);
					})
				)}
			</div>
		</div>
	);
}
