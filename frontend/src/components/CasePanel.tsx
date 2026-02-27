import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import CaseCard, { DispatchInfo } from "./CaseCard";
import { CaseInfo, CasePriority, PRIORITY_COLORS, ActiveView } from "./types";
import Badge from "./ui/Badge";
import EmptyState from "./ui/EmptyState";
import "./CasePanel.css";

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
	incidents,
	loading = false,
	onDispatch,
	dispatchLoading,
	dispatchInfoMap = {},
}: PanelProps): JSX.Element {
	const [showResolved, setShowResolved] = useState(false);

	const { active, resolved, priorityCounts } = useMemo(() => {
		const active: CaseInfo[] = [];
		const resolved: CaseInfo[] = [];
		const counts: Partial<Record<CasePriority, number>> = {};

		for (const c of incidents) {
			if (c.status === "resolved") {
				resolved.push(c);
			} else {
				active.push(c);
				counts[c.priority] = (counts[c.priority] || 0) + 1;
			}
		}

		// Sort active: by weight desc (most urgent), then by reported_at asc (oldest first)
		active.sort((a, b) => {
			if (b.weight !== a.weight) return b.weight - a.weight;
			return new Date(a.reported_at).getTime() - new Date(b.reported_at).getTime();
		});

		resolved.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

		return { active, resolved, priorityCounts: counts };
	}, [incidents]);

	return (
		<div className="dp-section">
			{/* Priority summary */}
			<div className="dp-priority-summary">
				{(["Purple", "Red", "Orange", "Yellow", "Green"] as CasePriority[]).map(p => {
					const count = priorityCounts[p];
					if (!count) return null;
					return (
						<Badge key={p} variant="priority" size="sm" dot color={PRIORITY_COLORS[p]}>
							{count} {p}
						</Badge>
					);
				})}
			</div>

			{/* Active Cases */}
			<div className="dp-case-list">
				{loading ? (
					<EmptyState title="Loading incidents..." />
				) : active.length === 0 ? (
					<EmptyState title="No active incidents" description="New incidents will appear here automatically." />
				) : (
					active.map(c => (
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

			{/* Resolved Cases */}
			{resolved.length > 0 && (
				<div className="dp-resolved">
					<button className="dp-resolved-toggle" onClick={() => setShowResolved(!showResolved)}>
						<ChevronDown size={14} style={{ transform: showResolved ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 150ms' }} />
						<span>Resolved</span>
						<Badge variant="neutral" size="sm">{resolved.length}</Badge>
					</button>
					{showResolved && (
						<div className="dp-case-list dp-resolved-list">
							{resolved.map(c => (
								<CaseCard key={c.id} data={c} dispatchInfo={dispatchInfoMap[c.id]} />
							))}
						</div>
					)}
				</div>
			)}
		</div>
	);
}
