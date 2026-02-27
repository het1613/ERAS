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
	const [showPast, setShowPast] = useState(true);

	const { active, past, priorityCounts } = useMemo(() => {
		const active: CaseInfo[] = [];
		const past: CaseInfo[] = [];
		const counts: Partial<Record<CasePriority, number>> = {};

		for (const c of incidents) {
			if (c.status === "resolved") {
				past.push(c);
			} else {
				active.push(c);
				counts[c.priority] = (counts[c.priority] || 0) + 1;
			}
		}

		active.sort((a, b) => {
			if (b.weight !== a.weight) return b.weight - a.weight;
			return new Date(a.reported_at).getTime() - new Date(b.reported_at).getTime();
		});

		past.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

		return { active, past, priorityCounts: counts };
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
			<div className="dp-section-header">
				<span className="dp-section-title">Active Cases</span>
				{active.length > 0 && <Badge variant="warning" size="sm">{active.length}</Badge>}
			</div>
			<div className="dp-case-list">
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

			{/* Past Cases */}
			<div className="dp-section-header dp-past-header">
				<button className="dp-resolved-toggle" onClick={() => setShowPast(!showPast)}>
					<ChevronDown size={14} style={{ transform: showPast ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 150ms' }} />
					<span className="dp-section-title">Past Cases</span>
					<Badge variant="neutral" size="sm">{past.length}</Badge>
				</button>
			</div>
			{showPast && past.length > 0 && (
				<div className="dp-case-list dp-past-list">
					{past.map(c => (
						<CaseCard key={c.id} data={c} dispatchInfo={dispatchInfoMap[c.id]} />
					))}
				</div>
			)}
		</div>
	);
}
