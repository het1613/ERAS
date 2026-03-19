import { useDispatchTest } from "../contexts/DispatchTestContext";
import "./ui/ConfirmDialog.css";

export default function TestConsentModal() {
	const { consentModalOpen, phase, confirmConsent, cancelConsent } =
		useDispatchTest();

	if (!consentModalOpen) return null;

	const isResetting = phase === "resetting";

	return (
		<div className="eras-dialog-overlay">
			<div className="eras-dialog" style={{ maxWidth: 520 }}>
				<div className="eras-dialog-header">
					<span className="eras-dialog-title">
						{isResetting ? "Preparing Test..." : "Dispatch Performance Study"}
					</span>
				</div>
				<div className="eras-dialog-body">
					{isResetting ? (
						<p style={{ margin: 0 }}>
							Resetting the system. Please wait patiently while we prepare the
							test environment...
						</p>
					) : (
						<>
							<p style={{ margin: "0 0 12px 0" }}>
								You are about to begin a dispatch performance study consisting
								of <strong>two rounds</strong>.
							</p>
							<p style={{ margin: "0 0 12px 0" }}>
								In each round, you will dispatch 6 emergency incidents. One round
								will use <strong>optimizer-assisted</strong> dispatch and the other
								will use <strong>manual</strong> dispatch. The order is randomized.
							</p>
							<p style={{ margin: "0 0 12px 0" }}>
								After each round, you will complete a brief workload survey
								(NASA TLX). At the end, you will see a comparison of your
								performance across both rounds.
							</p>
							<p style={{ margin: "0 0 12px 0", fontWeight: 500 }}>
								Your response times, dispatch decisions, and survey responses
								will be recorded for research purposes.
							</p>
							<p style={{ margin: 0 }}>
								All existing data will be reset before the test begins.
							</p>
						</>
					)}
				</div>
				{!isResetting && (
					<div className="eras-dialog-footer">
						<button
							onClick={cancelConsent}
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
							I Decline
						</button>
						<button
							onClick={confirmConsent}
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
							I Agree
						</button>
					</div>
				)}
			</div>
		</div>
	);
}
