import { useDispatchTest } from "../contexts/DispatchTestContext";
import "./ui/ConfirmDialog.css";

export default function TestConsentModal() {
	const { consentModalOpen, phase, confirmConsent, cancelConsent } =
		useDispatchTest();

	if (!consentModalOpen) return null;

	const isResetting = phase === "resetting";

	return (
		<div className="eras-dialog-overlay">
			<div className="eras-dialog" style={{ maxWidth: 480 }}>
				<div className="eras-dialog-header">
					<span className="eras-dialog-title">
						{isResetting ? "Preparing Test..." : "Dispatch Performance Test"}
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
								You are about to begin a <strong>5-minute</strong> dispatch
								performance test.
							</p>
							<p style={{ margin: "0 0 12px 0" }}>
								We will simulate incoming emergency incidents and measure your
								performance in a simulated dispatch environment. Your response
								times and decisions will be recorded.
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
