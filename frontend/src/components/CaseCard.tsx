import { MapPin, Clock, Truck } from "lucide-react";
import { CaseInfo, PRIORITY_COLORS, PRIORITY_BGS, CasePriority } from "./types";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import "./CasePanel.css";

export type DispatchPhase =
	| "finding"
	| "suggested"
	| "dispatched"
	| "en_route"
	| "on_scene"
	| "arrived"
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
	{ key: "arrived", label: "Resolved" },
];

const STATUS_LABELS: Record<string, string> = {
	open: "Open",
	in_progress: "In Progress",
	resolved: "Resolved",
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

function getPhaseIndex(phase: DispatchPhase | undefined, status: string): number {
	if (status === "resolved") return 4;
	if (!phase) return 0;
	const map: Record<string, number> = { finding: 0, suggested: 0, dispatched: 1, en_route: 2, on_scene: 3, arrived: 4 };
	return map[phase] ?? 0;
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
						variant={data.status === "open" ? "info" : data.status === "in_progress" ? "warning" : "neutral"}
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

			{/* Vehicle Assignment */}
			{dispatchInfo?.vehicleId && (
				<div className="cc-vehicle">
					<Truck size={12} />
					<span>{formatVehicleLabel(dispatchInfo.vehicleId)}</span>
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
