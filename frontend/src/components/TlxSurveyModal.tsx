import { useState } from "react";
import { useDispatchTest } from "../contexts/DispatchTestContext";
import "./ui/ConfirmDialog.css";

interface TlxScores {
	mentalDemand: number;
	physicalDemand: number;
	temporalDemand: number;
	effort: number;
	performance: number;
	frustration: number;
}

const TLX_DIMENSIONS = [
	{
		key: "mentalDemand" as const,
		label: "Mental Demand",
		question: "How mentally demanding was the task?",
		lowLabel: "Low",
		highLabel: "High",
	},
	{
		key: "physicalDemand" as const,
		label: "Physical Demand",
		question: "How physically demanding was the task?",
		lowLabel: "Low",
		highLabel: "High",
	},
	{
		key: "temporalDemand" as const,
		label: "Temporal Demand",
		question: "How hurried or rushed was the pace of the task?",
		lowLabel: "Low",
		highLabel: "High",
	},
	{
		key: "effort" as const,
		label: "Effort",
		question:
			"How hard did you have to work to accomplish your level of performance?",
		lowLabel: "Low",
		highLabel: "High",
	},
	{
		key: "performance" as const,
		label: "Performance",
		question:
			"How successful were you in accomplishing what you were asked to do?",
		lowLabel: "Good",
		highLabel: "Poor",
	},
	{
		key: "frustration" as const,
		label: "Frustration",
		question:
			"How insecure, discouraged, irritated, stressed, and annoyed were you?",
		lowLabel: "Low",
		highLabel: "High",
	},
];

const DEFAULT_SCORES: TlxScores = {
	mentalDemand: 50,
	physicalDemand: 50,
	temporalDemand: 50,
	effort: 50,
	performance: 50,
	frustration: 50,
};

export default function TlxSurveyModal() {
	const { phase, currentRound, roundOrder, submitTlx } = useDispatchTest();
	const [scores, setScores] = useState<TlxScores>({ ...DEFAULT_SCORES });

	if (phase !== "tlx") return null;

	const mode = roundOrder[currentRound - 1];
	const modeLabel = mode === "manual" ? "Manual" : "Optimizer";

	const handleChange = (key: keyof TlxScores, value: number) => {
		setScores((prev) => ({ ...prev, [key]: value }));
	};

	const handleSubmit = () => {
		submitTlx(scores);
		setScores({ ...DEFAULT_SCORES });
	};

	return (
		<div className="eras-dialog-overlay">
			<div className="eras-dialog" style={{ maxWidth: 560 }}>
				<div className="eras-dialog-header">
					<span className="eras-dialog-title">
						Workload Assessment — Round {currentRound} ({modeLabel} Mode)
					</span>
				</div>
				<div className="eras-dialog-body">
					<p style={{ margin: "0 0 16px 0", color: "var(--text-secondary)" }}>
						Please rate your experience for the round you just completed.
					</p>
					<div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
						{TLX_DIMENSIONS.map((dim) => (
							<div key={dim.key}>
								<div
									style={{
										display: "flex",
										justifyContent: "space-between",
										alignItems: "baseline",
										marginBottom: 4,
									}}
								>
									<span
										style={{
											fontWeight: 600,
											fontSize: "var(--text-sm)",
											color: "var(--text-primary)",
										}}
									>
										{dim.label}
									</span>
									<span
										style={{
											fontSize: "var(--text-xs)",
											color: "var(--text-tertiary)",
											fontVariantNumeric: "tabular-nums",
										}}
									>
										{scores[dim.key]}
									</span>
								</div>
								<p
									style={{
										margin: "0 0 6px 0",
										fontSize: "var(--text-xs)",
										color: "var(--text-tertiary)",
									}}
								>
									{dim.question}
								</p>
								<div
									style={{
										display: "flex",
										alignItems: "center",
										gap: 8,
									}}
								>
									<span
										style={{
											fontSize: "var(--text-xs)",
											color: "var(--text-tertiary)",
											minWidth: 32,
											textAlign: "right",
										}}
									>
										{dim.lowLabel}
									</span>
									<input
										type="range"
										min={0}
										max={100}
										step={5}
										value={scores[dim.key]}
										onChange={(e) =>
											handleChange(dim.key, Number(e.target.value))
										}
										style={{ flex: 1 }}
									/>
									<span
										style={{
											fontSize: "var(--text-xs)",
											color: "var(--text-tertiary)",
											minWidth: 32,
										}}
									>
										{dim.highLabel}
									</span>
								</div>
							</div>
						))}
					</div>
				</div>
				<div className="eras-dialog-footer">
					<button
						onClick={handleSubmit}
						style={{
							padding: "6px 16px",
							borderRadius: "var(--radius-md)",
							border: "1px solid transparent",
							background: "var(--accent-blue)",
							color: "#fff",
							fontWeight: 500,
							fontSize: "var(--text-sm)",
							cursor: "pointer",
						}}
					>
						{currentRound === 1 ? "Submit & Start Round 2" : "Submit & View Results"}
					</button>
				</div>
			</div>
		</div>
	);
}
