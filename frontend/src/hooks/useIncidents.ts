import { useState, useEffect, useRef, useCallback } from "react";
import { CaseInfo } from "../components/types";
import { useWebSocket } from "../contexts/WebSocketContext";

interface UseIncidentsOptions {
	onNewIncident?: (incident: CaseInfo) => void;
}

interface UseIncidentsResult {
	incidents: CaseInfo[];
	connected: boolean;
	loading: boolean;
}

/** CaseInfo + a monotonic client-side counter so we can sort newest-first reliably. */
interface TrackedIncident {
	incident: CaseInfo;
	seq: number;
}

let nextSeq = 0;

export function useIncidents(options?: UseIncidentsOptions): UseIncidentsResult {
	const onNewIncidentRef = useRef(options?.onNewIncident);
	onNewIncidentRef.current = options?.onNewIncident;
	const [incidentMap, setIncidentMap] = useState<Map<string, TrackedIncident>>(
		new Map()
	);
	const [loading, setLoading] = useState(true);

	const { connected, subscribe } = useWebSocket();
	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	useEffect(() => {
		async function fetchIncidents() {
			try {
				const res = await fetch(`${apiUrl}/incidents`);
				if (!res.ok) throw new Error(`HTTP ${res.status}`);
				const data = await res.json();
				const fetched: CaseInfo[] = data.incidents ?? data;
				const map = new Map<string, TrackedIncident>();
				for (const inc of fetched) {
					map.set(inc.id, { incident: inc, seq: nextSeq++ });
				}
				setIncidentMap(map);
			} catch (err) {
				console.error("Failed to fetch incidents:", err);
			} finally {
				setLoading(false);
			}
		}
		fetchIncidents();
	}, [apiUrl]);

	const handleMessage = useCallback((msg: { type: string; data: any }) => {
		if (msg.type === "system_reset") {
			setIncidentMap(new Map());
			return;
		}
		if (msg.type === "incident_created" || msg.type === "incident_updated") {
			const incident: CaseInfo = msg.data;
			setIncidentMap((prev) => {
				const next = new Map(prev);
				const existing = prev.get(incident.id);
				next.set(incident.id, {
					incident,
					seq: existing ? existing.seq : nextSeq++,
				});
				return next;
			});
			if (msg.type === "incident_created" && onNewIncidentRef.current) {
				onNewIncidentRef.current(incident);
			}
		}
	}, []);

	useEffect(() => {
		return subscribe(handleMessage);
	}, [subscribe, handleMessage]);

	const incidents = Array.from(incidentMap.values())
		.sort((a, b) => b.seq - a.seq)
		.map((t) => t.incident);

	return {
		incidents,
		connected,
		loading,
	};
}
