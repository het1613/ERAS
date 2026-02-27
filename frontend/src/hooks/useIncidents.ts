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

export function useIncidents(options?: UseIncidentsOptions): UseIncidentsResult {
	const onNewIncidentRef = useRef(options?.onNewIncident);
	onNewIncidentRef.current = options?.onNewIncident;
	const [incidentMap, setIncidentMap] = useState<Map<string, CaseInfo>>(
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
				const incidents: CaseInfo[] = data.incidents ?? data;
				const map = new Map<string, CaseInfo>();
				for (const inc of incidents) {
					map.set(inc.id, inc);
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
				next.set(incident.id, incident);
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

	return {
		incidents: Array.from(incidentMap.values()),
		connected,
		loading,
	};
}
