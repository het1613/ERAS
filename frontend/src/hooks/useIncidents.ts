import { useState, useEffect, useRef, useCallback } from "react";
import { CaseInfo } from "../components/types";

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
	const [connected, setConnected] = useState(false);
	const [loading, setLoading] = useState(true);
	const wsRef = useRef<WebSocket | null>(null);

	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	// Fetch initial incident list via REST
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

	// WebSocket for live incident updates
	const handleMessage = useCallback((event: MessageEvent) => {
		try {
			const msg = JSON.parse(event.data);
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
		} catch (err) {
			console.error("Error parsing incident WS message:", err);
		}
	}, []);

	useEffect(() => {
		const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws";
		const ws = new WebSocket(wsUrl);

		ws.onopen = () => setConnected(true);
		ws.onclose = () => setConnected(false);
		ws.onerror = (err) => console.error("Incident WS error:", err);
		ws.onmessage = handleMessage;

		wsRef.current = ws;

		return () => {
			ws.close();
		};
	}, [apiUrl, handleMessage]);

	return {
		incidents: Array.from(incidentMap.values()),
		connected,
		loading,
	};
}
