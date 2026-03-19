import { useDispatchTest } from "../contexts/DispatchTestContext";
import { PRIORITY_COLORS, CasePriority } from "./types";
import "./ui/ConfirmDialog.css";

export default function TestResultsModal() {
	const { phase, incidents, dismissResults } = useDispatchTest();

	if (phase !== "complete") return null;

	const dispatched = incidents.filter((t) => t.dispatchedAt !== null);
	const avgTime =
		dispatched.length > 0
			? dispatched.reduce(
					(sum, t) => sum + (t.dispatchedAt! - t.createdAt),
					0
				) /
				dispatched.length /
				1000
			: 0;

	return (
		<div className="eras-dialog-overlay">
			<div className="eras-dialog" style={{ maxWidth: 560 }}>
				<div className="eras-dialog-header">
					<span className="eras-dialog-title">Dispatch Test Results</span>
				</div>
				<div className="eras-dialog-body">
					<table
						style={{
							width: "100%",
							borderCollapse: "collapse",
							fontSize: "var(--text-sm)",
						}}
					>
						<thead>
							<tr
								style={{
									borderBottom: "1px solid var(--border-default)",
									textAlign: "left",
								}}
							>
								<th style={{ padding: "6px 8px", fontWeight: 600 }}>#</th>
								<th style={{ padding: "6px 8px", fontWeight: 600 }}>
									Priority
								</th>
								<th style={{ padding: "6px 8px", fontWeight: 600 }}>Type</th>
								<th style={{ padding: "6px 8px", fontWeight: 600 }}>
									Location
								</th>
								<th
									style={{
										padding: "6px 8px",
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
										<td style={{ padding: "6px 8px" }}>{i + 1}</td>
										<td style={{ padding: "6px 8px" }}>
											<span style={{ display: "flex", alignItems: "center", gap: 6 }}>
												<span
													style={{
														width: 8,
														height: 8,
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
										<td style={{ padding: "6px 8px" }}>{inc.type}</td>
										<td
											style={{
												padding: "6px 8px",
												maxWidth: 160,
												overflow: "hidden",
												textOverflow: "ellipsis",
												whiteSpace: "nowrap",
											}}
										>
											{inc.location}
										</td>
										<td
											style={{
												padding: "6px 8px",
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
							{dispatched.length > 0 && (
								<tr style={{ borderTop: "2px solid var(--border-default)" }}>
									<td
										colSpan={4}
										style={{
											padding: "8px 8px",
											fontWeight: 600,
											textAlign: "right",
										}}
									>
										Average
									</td>
									<td
										style={{
											padding: "8px 8px",
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
