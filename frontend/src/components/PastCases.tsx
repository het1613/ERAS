import { useMemo } from "react";
import { useIncidents } from "../hooks/useIncidents";
import CaseCard from "./CaseCard";
import { CaseInfo } from "./types";
import EmptyState from "./ui/EmptyState";
import "./PastCases.css";

export default function PastCases() {
	const { incidents, loading } = useIncidents();

	const pastCases = useMemo(() => {
		const past: CaseInfo[] = incidents.filter(c => c.status === "resolved");
		past.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
		return past;
	}, [incidents]);

	return (
		<div className="past-cases">
			<div className="past-cases-header">
				<span className="past-cases-title">Past Cases</span>
				<span className="past-cases-count">{pastCases.length}</span>
			</div>
			<div className="past-cases-list">
				{loading ? (
					<EmptyState title="Loading cases..." />
				) : pastCases.length === 0 ? (
					<EmptyState title="No past cases" description="Resolved cases will appear here." />
				) : (
					pastCases.map(c => (
						<CaseCard key={c.id} data={c} />
					))
				)}
			</div>
		</div>
	);
}
