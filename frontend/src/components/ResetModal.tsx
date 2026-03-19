import { useDispatchTest } from "../contexts/DispatchTestContext";
import "./ui/ConfirmDialog.css";

export default function ResetModal() {
	const { phase, testLocked, consentModalOpen, currentRound, roundOrder } =
		useDispatchTest();

	// Show only during between-round resets (not the initial consent reset)
	if (phase !== "resetting" || !testLocked || consentModalOpen) return null;

	const mode = roundOrder[currentRound - 1];
	const modeLabel = mode === "manual" ? "Manual" : "Optimizer";

	return (
		<div className="eras-dialog-overlay">
			<div className="eras-dialog" style={{ maxWidth: 440 }}>
				<div className="eras-dialog-header">
					<span className="eras-dialog-title">Preparing Round {currentRound}</span>
				</div>
				<div className="eras-dialog-body">
					<p style={{ margin: "0 0 12px 0" }}>
						Resetting the system for <strong>Round {currentRound}</strong> ({modeLabel} Mode).
					</p>
					<p style={{ margin: 0, color: "var(--text-tertiary)" }}>
						Please wait — this will only take a moment...
					</p>
				</div>
			</div>
		</div>
	);
}
