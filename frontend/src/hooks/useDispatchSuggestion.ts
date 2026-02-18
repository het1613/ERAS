import { useState, useCallback, useEffect, useRef } from "react";
import { DispatchSuggestion } from "../components/types";

interface UseDispatchSuggestionResult {
	suggestion: DispatchSuggestion | null;
	loading: boolean;
	findBest: (incidentId: string) => Promise<void>;
	accept: () => Promise<void>;
	decline: () => Promise<void>;
	declineAndReassign: () => Promise<void>;
}

function parseSuggestionData(data: any): DispatchSuggestion {
	const routePreview = (data.route_preview || []).map(
		(point: [number, number]) => ({ lat: point[0], lng: point[1] })
	);
	return {
		suggestionId: data.suggestion_id,
		vehicleId: data.suggested_vehicle_id,
		incidentId: data.incident?.id || "",
		incident: data.incident,
		routePreview,
	};
}

export function useDispatchSuggestion(): UseDispatchSuggestionResult {
	const [suggestion, setSuggestion] = useState<DispatchSuggestion | null>(null);
	const [loading, setLoading] = useState(false);
	const wsRef = useRef<WebSocket | null>(null);

	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	// Listen for server-pushed dispatch_suggestion messages via WebSocket
	useEffect(() => {
		const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws";
		const ws = new WebSocket(wsUrl);

		ws.onmessage = (event) => {
			try {
				const msg = JSON.parse(event.data);
				if (msg.type === "dispatch_suggestion" && msg.data) {
					const parsed = parseSuggestionData(msg.data);
					setSuggestion(parsed);
					setLoading(false);
				}
			} catch (err) {
				console.error("Error parsing dispatch_suggestion WS message:", err);
			}
		};

		wsRef.current = ws;

		return () => {
			ws.close();
		};
	}, [apiUrl]);

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
			setSuggestion(parseSuggestionData(data));
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

	const declineAndReassign = useCallback(async () => {
		if (!suggestion) return;
		setLoading(true);
		try {
			const res = await fetch(
				`${apiUrl}/assignments/${suggestion.suggestionId}/decline-and-reassign`,
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						incident_id: suggestion.incidentId,
						declined_vehicle_id: suggestion.vehicleId,
					}),
				}
			);
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				throw new Error(err.detail || `HTTP ${res.status}`);
			}
			const data = await res.json();
			if (data.status === "no_vehicles_available") {
				alert("No more available vehicles to assign.");
				setSuggestion(null);
				setLoading(false);
			}
			// The new suggestion will arrive via WebSocket (dispatch_suggestion)
			// so we don't need to set it here — the WS handler will do it
		} catch (err) {
			console.error("Failed to decline and reassign:", err);
			alert(err instanceof Error ? err.message : "Failed to reassign");
			setSuggestion(null);
			setLoading(false);
		}
	}, [apiUrl, suggestion]);

	return { suggestion, loading, findBest, accept, decline, declineAndReassign };
}
