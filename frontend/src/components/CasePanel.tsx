import { useMemo, useRef, useEffect } from "react";
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
	focusedIncidentId?: string | null;
}

export default function CasesPanel({
	incidents,
	loading = false,
	onDispatch,
	dispatchLoading,
	dispatchInfoMap = {},
	focusedIncidentId,
}: PanelProps): JSX.Element {
	const caseListRef = useRef<HTMLDivElement>(null);

	const { active, priorityCounts } = useMemo(() => {
		const active: CaseInfo[] = [];
		const counts: Partial<Record<CasePriority, number>> = {};

		for (const c of incidents) {
			if (c.status !== "resolved") {
				active.push(c);
				counts[c.priority] = (counts[c.priority] || 0) + 1;
			}
		}

		active.sort((a, b) => {
			if (focusedIncidentId) {
				if (a.id === focusedIncidentId) return -1;
				if (b.id === focusedIncidentId) return 1;
			}
			if (b.weight !== a.weight) return b.weight - a.weight;
			return new Date(a.reported_at).getTime() - new Date(b.reported_at).getTime();
		});

		return { active, priorityCounts: counts };
	}, [incidents, focusedIncidentId]);

	useEffect(() => {
		if (focusedIncidentId && caseListRef.current) {
			caseListRef.current.scrollTo({ top: 0, behavior: "smooth" });
		}
	}, [focusedIncidentId]);

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
			<div className="dp-section-header">
				<span className="dp-section-title">Active Cases</span>
				{active.length > 0 && <Badge variant="warning" size="sm">{active.length}</Badge>}
			</div>
			<div className="dp-case-list" ref={caseListRef}>
				{loading ? (
					<EmptyState title="Loading incidents..." />
				) : active.length === 0 ? (
					<EmptyState title="No active incidents" description="New incidents will appear here when passed from call taker." />
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

		</div>
	);
}
