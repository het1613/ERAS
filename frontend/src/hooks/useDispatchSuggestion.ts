import { useState, useCallback } from "react";
import { DispatchSuggestion } from "../components/types";

interface UseDispatchSuggestionResult {
	suggestion: DispatchSuggestion | null;
	loading: boolean;
	findBest: (incidentId: string) => Promise<void>;
	accept: () => Promise<void>;
	decline: () => Promise<void>;
}

export function useDispatchSuggestion(): UseDispatchSuggestionResult {
	const [suggestion, setSuggestion] = useState<DispatchSuggestion | null>(null);
	const [loading, setLoading] = useState(false);

	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	const findBest = useCallback(async (incidentId: string) => {
		setLoading(true);
		try {
			const res = await fetch(`${apiUrl}/assignments/find-best`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ incident_id: incidentId }),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				throw new Error(err.detail || `HTTP ${res.status}`);
			}
			const data = await res.json();
			const routePreview = (data.route_preview || []).map(
				(point: [number, number]) => ({ lat: point[0], lng: point[1] })
			);
			setSuggestion({
				suggestionId: data.suggestion_id,
				vehicleId: data.suggested_vehicle_id,
				incidentId,
				incident: data.incident,
				routePreview,
			});
		} catch (err) {
			console.error("Failed to find best assignment:", err);
			alert(err instanceof Error ? err.message : "Failed to find assignment");
		} finally {
			setLoading(false);
		}
	}, [apiUrl]);

	const accept = useCallback(async () => {
		if (!suggestion) return;
		try {
			const res = await fetch(
				`${apiUrl}/assignments/${suggestion.suggestionId}/accept`,
				{ method: "POST" }
			);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
		} catch (err) {
			console.error("Failed to accept assignment:", err);
		} finally {
			setSuggestion(null);
		}
	}, [apiUrl, suggestion]);

	const decline = useCallback(async () => {
		if (!suggestion) return;
		try {
			const res = await fetch(
				`${apiUrl}/assignments/${suggestion.suggestionId}/decline`,
				{ method: "POST" }
			);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
		} catch (err) {
			console.error("Failed to decline assignment:", err);
		} finally {
			setSuggestion(null);
		}
	}, [apiUrl, suggestion]);

	return { suggestion, loading, findBest, accept, decline };
}
