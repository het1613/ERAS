import { MapPin, Clock, Truck } from "lucide-react";
import { CaseInfo, CaseStatus, PRIORITY_COLORS, PRIORITY_BGS, CasePriority } from "./types";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import "./CasePanel.css";

export type DispatchPhase =
	| "finding"
	| "suggested"
	| "dispatched"
	| "en_route"
	| "on_scene"
	| "transporting"
	| "at_hospital"
	| "resolved"
	| null;

export interface DispatchInfo {
	phase: DispatchPhase;
	vehicleId?: string;
}

const DISPATCH_PHASES: { key: string; label: string }[] = [
	{ key: "open", label: "Open" },
	{ key: "dispatched", label: "Dispatched" },
	{ key: "en_route", label: "En Route" },
	{ key: "on_scene", label: "On Scene" },
	{ key: "transporting", label: "Transporting" },
	{ key: "at_hospital", label: "At Hospital" },
	{ key: "resolved", label: "Resolved" },
];

const STATUS_LABELS: Record<string, string> = {
	open: "Open",
	dispatched: "Dispatched",
	en_route: "En Route",
	on_scene: "On Scene",
	transporting: "Transporting",
	at_hospital: "At Hospital",
	resolved: "Resolved",
};

const STATUS_VARIANTS: Record<string, "info" | "warning" | "neutral" | "success"> = {
	open: "info",
	dispatched: "warning",
	en_route: "warning",
	on_scene: "warning",
	transporting: "warning",
	at_hospital: "warning",
	resolved: "neutral",
};

function formatVehicleLabel(vehicleId: string): string {
	return vehicleId.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function timeAgo(isoString: string | undefined): string {
	if (!isoString) return "";
	const diff = Date.now() - new Date(isoString).getTime();
	const mins = Math.floor(diff / 60000);
	if (mins < 1) return "Just now";
	if (mins < 60) return `${mins}m ago`;
	const hrs = Math.floor(mins / 60);
	return `${hrs}h ${mins % 60}m ago`;
}

const PHASE_ORDER: Record<string, number> = {
	open: 0, finding: 0, suggested: 0,
	dispatched: 1, en_route: 2, on_scene: 3,
	transporting: 4, at_hospital: 5, resolved: 6,
};

function getPhaseIndex(phase: DispatchPhase | undefined, status: CaseStatus): number {
	if (status === "resolved") return 6;
	if (phase && PHASE_ORDER[phase] !== undefined) return PHASE_ORDER[phase];
	if (PHASE_ORDER[status] !== undefined) return PHASE_ORDER[status];
	return 0;
}

interface CaseCardProps {
	data: CaseInfo;
	onDispatch?: (incidentId: string) => void;
	dispatchLoading?: boolean;
	dispatchInfo?: DispatchInfo;
}

export default function CaseCard({ data, onDispatch, dispatchLoading, dispatchInfo }: CaseCardProps) {
	const phase = dispatchInfo?.phase;
	const priority = data.priority as CasePriority;
	const phaseIdx = getPhaseIndex(phase, data.status);
	const showProgress = data.status !== "open" || phase;
	const vehicleId = dispatchInfo?.vehicleId || data.assigned_vehicle_id;

	return (
		<div className="cc-card" style={{ borderLeftColor: PRIORITY_COLORS[priority] }}>
			{/* Row 1: Type + Badges */}
			<div className="cc-row-top">
				<span className="cc-type">{data.type}</span>
				<div className="cc-badges">
					<Badge
						variant="priority"
						size="sm"
						dot
						color={PRIORITY_COLORS[priority]}
						bg={PRIORITY_BGS[priority]}
					>
						{priority}
					</Badge>
					<Badge
						variant={STATUS_VARIANTS[data.status] || "neutral"}
						size="sm"
					>
						{STATUS_LABELS[data.status] || data.status}
					</Badge>
				</div>
			</div>

			{/* Row 2: Location + Time */}
			<div className="cc-details">
				<div className="cc-detail">
					<MapPin size={12} className="cc-detail-icon" />
					<span>{data.location || "Unknown location"}</span>
				</div>
				<div className="cc-detail">
					<Clock size={12} className="cc-detail-icon" />
					<span>{timeAgo(data.reported_at)}</span>
				</div>
			</div>

			{/* Progress Bar */}
			{showProgress && (
				<div className="cc-progress">
					{DISPATCH_PHASES.map((p, i) => (
						<div key={p.key} className={`cc-progress-step ${i <= phaseIdx ? "active" : ""} ${i === phaseIdx ? "current" : ""}`}>
							<div className="cc-progress-dot" />
							{i < DISPATCH_PHASES.length - 1 && <div className="cc-progress-line" />}
						</div>
					))}
				</div>
			)}

			{/* Progress Labels */}
			{showProgress && (
				<div className="cc-progress-labels">
					{DISPATCH_PHASES.map((p, i) => (
						<span key={p.key} className={`cc-progress-label ${i === phaseIdx ? "current" : ""}`}>
							{p.label}
						</span>
					))}
				</div>
			)}

			{/* Vehicle Assignment */}
			{vehicleId && (
				<div className="cc-vehicle">
					<Truck size={12} />
					<span>{formatVehicleLabel(vehicleId)}</span>
				</div>
			)}

			{/* Dispatch Button */}
			{data.status === "open" && !phase && onDispatch && (
				<Button
					variant="primary"
					size="sm"
					fullWidth
					loading={dispatchLoading}
					onClick={() => onDispatch(data.id)}
					style={{ marginTop: 'var(--space-3)' }}
				>
					Dispatch
				</Button>
			)}
		</div>
	);
}
