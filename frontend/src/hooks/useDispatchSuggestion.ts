import { useState, useCallback, useEffect, useMemo } from "react";
import { DispatchSuggestion } from "../components/types";
import { useWebSocket } from "../contexts/WebSocketContext";

interface UseDispatchSuggestionResult {
	suggestion: DispatchSuggestion | null;
	loading: boolean;
	queueLength: number;
	findBest: (incidentId: string) => Promise<void>;
	preview: (incidentId: string, vehicleId: string) => Promise<void>;
	accept: () => Promise<void>;
	decline: () => Promise<void>;
	declineAndReassign: () => Promise<void>;
}

function parseSuggestionData(data: any): DispatchSuggestion {
	const routePreview = (data.route_preview || []).map(
		(point: [number, number]) => ({ lat: point[0], lng: point[1] })
	);

	const result: DispatchSuggestion = {
		suggestionId: data.suggestion_id,
		vehicleId: data.suggested_vehicle_id,
		incidentId: data.incident?.id || "",
		incident: data.incident,
		routePreview,
		hospital: data.hospital || undefined,
		durationSeconds: data.duration_seconds || undefined,
	};

	if (data.is_reroute) {
		result.isReroute = true;
		result.preemptedIncident = {
			id: data.preempted_incident_id,
			priority: data.preempted_incident_priority,
			type: data.preempted_incident_type,
			location: data.preempted_incident_location,
		};
	}

	if (data.reassignment) {
		const reassignRoutePreview = (data.reassignment.route_preview || []).map(
			(point: [number, number]) => ({ lat: point[0], lng: point[1] })
		);
		result.reassignment = {
			vehicleId: data.reassignment.vehicle_id,
			incidentId: data.reassignment.incident_id,
			routePreview: reassignRoutePreview,
			durationSeconds: data.reassignment.duration_seconds || undefined,
		};
	}

	return result;
}

export function useDispatchSuggestion(): UseDispatchSuggestionResult {
	const [queue, setQueue] = useState<DispatchSuggestion[]>([]);
	const [loading, setLoading] = useState(false);

	const suggestion = useMemo(() => queue[0] || null, [queue]);
	const queueLength = queue.length;

	const { subscribe } = useWebSocket();
	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	useEffect(() => {
		return subscribe((msg) => {
			if (msg.type === "system_reset") {
				setQueue([]);
				setLoading(false);
				return;
			}
			if (msg.type === "dispatch_suggestion" && msg.data) {
				const parsed = parseSuggestionData(msg.data);
				setQueue((prev) => [...prev, parsed]);
				setLoading(false);
			}
		});
	}, [subscribe]);

	const findBest = useCallback(
		async (incidentId: string) => {
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
				setQueue((prev) => [...prev, parseSuggestionData(data)]);
			} catch (err) {
				console.error("Failed to find best assignment:", err);
				alert(
					err instanceof Error ? err.message : "Failed to find assignment"
				);
			} finally {
				setLoading(false);
			}
		},
		[apiUrl]
	);

	const preview = useCallback(
		async (incidentId: string, vehicleId: string) => {
			setLoading(true);
			try {
				const res = await fetch(`${apiUrl}/assignments/preview`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ incident_id: incidentId, vehicle_id: vehicleId }),
				});
				if (!res.ok) {
					const err = await res.json().catch(() => ({}));
					throw new Error(err.detail || `HTTP ${res.status}`);
				}
				const data = await res.json();
				// Replace current suggestion (user is picking a different ambulance)
				setQueue((prev) => {
					const rest = prev.length > 0 ? prev.slice(1) : [];
					return [parseSuggestionData(data), ...rest];
				});
			} catch (err) {
				console.error("Failed to preview assignment:", err);
				alert(
					err instanceof Error ? err.message : "Failed to preview assignment"
				);
			} finally {
				setLoading(false);
			}
		},
		[apiUrl]
	);

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
			setQueue((prev) => prev.slice(1));
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
			// Clear declined_vehicles so future dispatches for this incident start fresh
			await fetch(
				`${apiUrl}/incidents/${suggestion.incidentId}/clear-declined`,
				{ method: "POST" }
			).catch((err) =>
				console.error("Failed to clear declined vehicles:", err)
			);
		} catch (err) {
			console.error("Failed to decline assignment:", err);
		} finally {
			setQueue((prev) => prev.slice(1));
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
				setQueue((prev) => prev.slice(1));
				setLoading(false);
			}
		} catch (err) {
			console.error("Failed to decline and reassign:", err);
			alert(err instanceof Error ? err.message : "Failed to reassign");
			setQueue((prev) => prev.slice(1));
			setLoading(false);
		}
	}, [apiUrl, suggestion]);

	return {
		suggestion,
		loading,
		queueLength,
		findBest,
		preview,
		accept,
		decline,
		declineAndReassign,
	};
}
