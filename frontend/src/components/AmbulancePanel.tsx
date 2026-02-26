import { useMemo, useEffect, useRef } from "react";
import "./AmbulancePanel.css";
import AmbulanceCard from "./AmbulanceCard";

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

export type ActiveView = "Ambulances" | "Cases" | "Transcripts";

interface PanelProps {
	activeView: ActiveView;
	handleViewChange: (view: ActiveView) => void;
	units: UnitInfo[];
	onUnitClick: (unit: UnitInfo) => void;
	focusedUnitId?: string | null;
}

const STATUS_FILTER_ORDER: { key: UnitStatus; cssClass: string }[] = [
	{ key: "Available", cssClass: "available" },
	{ key: "Dispatched", cssClass: "dispatched" },
	{ key: "On-scene", cssClass: "onscene" },
	{ key: "Returning", cssClass: "returning" },
];

export default function AmbulancePanel({
	activeView,
	handleViewChange,
	units,
	onUnitClick,
	focusedUnitId,
}: PanelProps) {
	const unitListRef = useRef<HTMLDivElement | null>(null);

	const sortedUnits = useMemo(() => {
		if (!focusedUnitId) return units;
		return [...units].sort((a, b) => {
			if (a.id === focusedUnitId) return -1;
			if (b.id === focusedUnitId) return 1;
			return 0;
		});
	}, [units, focusedUnitId]);

	useEffect(() => {
		if (focusedUnitId && unitListRef.current) {
			unitListRef.current.scrollTop = 0;
		}
	}, [focusedUnitId]);

	const statusCounts = useMemo(() => {
		const counts: Record<string, number> = {};
		for (const u of units) {
			counts[u.status] = (counts[u.status] || 0) + 1;
		}
		return counts;
	}, [units]);

	return (
		<div className="dispatch-panel">
			<div className="top-nav">
				<h2 className="panel-title">Emergency Dispatch</h2>

				<div className="status-filters">
					{STATUS_FILTER_ORDER.map(({ key, cssClass }) => {
						const count = statusCounts[key] || 0;
						if (count === 0) return null;
						return (
							<button key={key} className={`filter ${cssClass}`}>
								{count} {key}
							</button>
						);
					})}
					<button className="filter all">All</button>
				</div>
			</div>

			<div className="active-units">
				<h3 className="section-title">Active Units</h3>

				{/* Unit List */}
				<div className="unit-list" ref={unitListRef}>
					{sortedUnits.map((u) => (
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
