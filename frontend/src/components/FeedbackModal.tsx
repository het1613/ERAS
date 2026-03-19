import { useState } from "react";
import { useDispatchTest } from "../contexts/DispatchTestContext";
import "./ui/ConfirmDialog.css";

export default function FeedbackModal() {
	const { phase, submitFeedback } = useDispatchTest();
	const [feedback, setFeedback] = useState("");
	const [submitting, setSubmitting] = useState(false);

	if (phase !== "feedback") return null;

	const handleSubmit = async () => {
		setSubmitting(true);
		await submitFeedback(feedback);
		setFeedback("");
		setSubmitting(false);
	};

	return (
		<div className="eras-dialog-overlay">
			<div className="eras-dialog" style={{ maxWidth: 520 }}>
				<div className="eras-dialog-header">
					<span className="eras-dialog-title">Thank You!</span>
				</div>
				<div className="eras-dialog-body">
					<p style={{ margin: "0 0 12px 0" }}>
						You have completed both rounds of the dispatch study. Thank you for
						your time and participation.
					</p>
					<p style={{ margin: "0 0 16px 0" }}>
						Before viewing your results, we'd love to hear any feedback or
						comments about your experience. Was one mode easier or more
						intuitive? Anything you found confusing or would improve?
					</p>
					<textarea
						value={feedback}
						onChange={(e) => setFeedback(e.target.value)}
						placeholder="Share any thoughts about the two dispatch modes, usability, or the study itself... (optional)"
						rows={5}
						style={{
							width: "100%",
							padding: "8px 10px",
							fontSize: "var(--text-sm)",
							borderRadius: "var(--radius-md)",
							border: "1px solid var(--border-default)",
							background: "var(--surface-base)",
							color: "var(--text-primary)",
							resize: "vertical",
							fontFamily: "inherit",
							boxSizing: "border-box",
						}}
					/>
				</div>
				<div className="eras-dialog-footer">
					<button
						onClick={handleSubmit}
						disabled={submitting}
						style={{
							padding: "6px 16px",
							borderRadius: "var(--radius-md)",
							border: "1px solid transparent",
							background: "var(--accent-blue)",
							color: "#fff",
							fontWeight: 500,
							fontSize: "var(--text-sm)",
							cursor: submitting ? "not-allowed" : "pointer",
							opacity: submitting ? 0.7 : 1,
						}}
					>
						{submitting ? "Submitting..." : "Submit & View Results"}
					</button>
				</div>
			</div>
		</div>
	);
}
