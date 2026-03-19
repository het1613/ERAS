import { useDispatchTest, TlxScores } from "../contexts/DispatchTestContext";
import { PRIORITY_COLORS, CasePriority } from "./types";
import "./ui/ConfirmDialog.css";

interface TestIncident {
	incidentId: string;
	priority: string;
	type: string;
	location: string;
	createdAt: number;
	dispatchedAt: number | null;
}

const TLX_LABELS = [
	{ key: "mentalDemand" as const, label: "Mental Demand" },
	{ key: "physicalDemand" as const, label: "Physical Demand" },
	{ key: "temporalDemand" as const, label: "Temporal Demand" },
	{ key: "effort" as const, label: "Effort" },
	{ key: "performance" as const, label: "Performance" },
	{ key: "frustration" as const, label: "Frustration" },
];

function computeAvgTime(incidents: TestIncident[]) {
	const dispatched = incidents.filter((t) => t.dispatchedAt !== null);
	if (dispatched.length === 0) return 0;
	return (
		dispatched.reduce((sum, t) => sum + (t.dispatchedAt! - t.createdAt), 0) /
		dispatched.length /
		1000
	);
}

function computeRawTlx(scores: TlxScores | null) {
	if (!scores) return 0;
	return (
		(scores.mentalDemand +
			scores.physicalDemand +
			scores.temporalDemand +
			scores.effort +
			scores.performance +
			scores.frustration) /
		6
	);
}

function RoundTable({
	roundNum,
	mode,
	incidents,
}: {
	roundNum: number;
	mode: string;
	incidents: TestIncident[];
}) {
	const avgTime = computeAvgTime(incidents);
	const modeLabel = mode === "manual" ? "Manual" : "Optimizer";

	return (
		<div style={{ marginBottom: 20 }}>
			<h3
				style={{
					margin: "0 0 8px 0",
					fontSize: "var(--text-sm)",
					fontWeight: 600,
					color: "var(--text-primary)",
				}}
			>
				Round {roundNum}: {modeLabel} Mode
			</h3>
			<table
				style={{
					width: "100%",
					borderCollapse: "collapse",
					fontSize: "var(--text-xs)",
				}}
			>
				<thead>
					<tr
						style={{
							borderBottom: "1px solid var(--border-default)",
							textAlign: "left",
						}}
					>
						<th style={{ padding: "4px 6px", fontWeight: 600 }}>#</th>
						<th style={{ padding: "4px 6px", fontWeight: 600 }}>Priority</th>
						<th style={{ padding: "4px 6px", fontWeight: 600 }}>Type</th>
						<th
							style={{
								padding: "4px 6px",
								fontWeight: 600,
								textAlign: "right",
							}}
						>
							Time (s)
						</th>
					</tr>
				</thead>
				<tbody>
					{incidents.map((inc, i) => {
						const time = inc.dispatchedAt
							? ((inc.dispatchedAt - inc.createdAt) / 1000).toFixed(1)
							: null;
						return (
							<tr
								key={inc.incidentId}
								style={{
									borderBottom: "1px solid var(--border-subtle)",
								}}
							>
								<td style={{ padding: "4px 6px" }}>{i + 1}</td>
								<td style={{ padding: "4px 6px" }}>
									<span
										style={{
											display: "flex",
											alignItems: "center",
											gap: 4,
										}}
									>
										<span
											style={{
												width: 7,
												height: 7,
												borderRadius: "50%",
												background:
													PRIORITY_COLORS[
														inc.priority as CasePriority
													] || "#999",
												flexShrink: 0,
											}}
										/>
										{inc.priority}
									</span>
								</td>
								<td style={{ padding: "4px 6px" }}>{inc.type}</td>
								<td
									style={{
										padding: "4px 6px",
										textAlign: "right",
										fontVariantNumeric: "tabular-nums",
										color: time ? "inherit" : "var(--accent-danger)",
										fontWeight: time ? 400 : 600,
									}}
								>
									{time ?? "Timed out"}
								</td>
							</tr>
						);
					})}
					{incidents.length > 0 && (
						<tr style={{ borderTop: "2px solid var(--border-default)" }}>
							<td
								colSpan={3}
								style={{
									padding: "6px 6px",
									fontWeight: 600,
									textAlign: "right",
								}}
							>
								Average
							</td>
							<td
								style={{
									padding: "6px 6px",
									textAlign: "right",
									fontWeight: 600,
									fontVariantNumeric: "tabular-nums",
								}}
							>
								{avgTime.toFixed(1)}
							</td>
						</tr>
					)}
				</tbody>
			</table>
		</div>
	);
}

export default function TestResultsModal() {
	const {
		phase,
		roundOrder,
		round1Incidents,
		round2Incidents,
		round1TlxScores,
		round2TlxScores,
		dismissResults,
	} = useDispatchTest();

	if (phase !== "complete") return null;

	const rawTlx1 = computeRawTlx(round1TlxScores);
	const rawTlx2 = computeRawTlx(round2TlxScores);

	return (
		<div className="eras-dialog-overlay">
			<div className="eras-dialog" style={{ maxWidth: 620, maxHeight: "90vh", overflow: "auto" }}>
				<div className="eras-dialog-header">
					<span className="eras-dialog-title">
						Study Results — Comparison
					</span>
				</div>
				<div className="eras-dialog-body">
					<RoundTable
						roundNum={1}
						mode={roundOrder[0]}
						incidents={round1Incidents}
					/>
					<RoundTable
						roundNum={2}
						mode={roundOrder[1]}
						incidents={round2Incidents}
					/>

					<h3
						style={{
							margin: "0 0 8px 0",
							fontSize: "var(--text-sm)",
							fontWeight: 600,
							color: "var(--text-primary)",
						}}
					>
						Workload Comparison (NASA TLX)
					</h3>
					<table
						style={{
							width: "100%",
							borderCollapse: "collapse",
							fontSize: "var(--text-xs)",
						}}
					>
						<thead>
							<tr
								style={{
									borderBottom: "1px solid var(--border-default)",
									textAlign: "left",
								}}
							>
								<th style={{ padding: "4px 6px", fontWeight: 600 }}>
									Dimension
								</th>
								<th
									style={{
										padding: "4px 6px",
										fontWeight: 600,
										textAlign: "right",
									}}
								>
									Round 1 ({roundOrder[0] === "manual" ? "Manual" : "Optimizer"})
								</th>
								<th
									style={{
										padding: "4px 6px",
										fontWeight: 600,
										textAlign: "right",
									}}
								>
									Round 2 ({roundOrder[1] === "manual" ? "Manual" : "Optimizer"})
								</th>
							</tr>
						</thead>
						<tbody>
							{TLX_LABELS.map((dim) => (
								<tr
									key={dim.key}
									style={{
										borderBottom: "1px solid var(--border-subtle)",
									}}
								>
									<td style={{ padding: "4px 6px" }}>{dim.label}</td>
									<td
										style={{
											padding: "4px 6px",
											textAlign: "right",
											fontVariantNumeric: "tabular-nums",
										}}
									>
										{round1TlxScores?.[dim.key] ?? "—"}
									</td>
									<td
										style={{
											padding: "4px 6px",
											textAlign: "right",
											fontVariantNumeric: "tabular-nums",
										}}
									>
										{round2TlxScores?.[dim.key] ?? "—"}
									</td>
								</tr>
							))}
							<tr
								style={{
									borderTop: "2px solid var(--border-default)",
								}}
							>
								<td
									style={{
										padding: "6px 6px",
										fontWeight: 600,
									}}
								>
									Overall Raw TLX
								</td>
								<td
									style={{
										padding: "6px 6px",
										textAlign: "right",
										fontWeight: 600,
										fontVariantNumeric: "tabular-nums",
									}}
								>
									{rawTlx1.toFixed(1)}
								</td>
								<td
									style={{
										padding: "6px 6px",
										textAlign: "right",
										fontWeight: 600,
										fontVariantNumeric: "tabular-nums",
									}}
								>
									{rawTlx2.toFixed(1)}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<div className="eras-dialog-footer">
					<button
						onClick={dismissResults}
						style={{
							padding: "6px 16px",
							borderRadius: "var(--radius-md)",
							border: "1px solid var(--border-default)",
							background: "var(--surface-elevated)",
							color: "var(--text-primary)",
							fontWeight: 500,
							fontSize: "var(--text-sm)",
							cursor: "pointer",
						}}
					>
						Close
					</button>
				</div>
			</div>
		</div>
	);
}
