import { useState, useEffect, useRef, useCallback } from "react";
import { VehicleData } from "../components/AmbulancePanel";

interface UseVehicleUpdatesResult {
	vehicles: VehicleData[];
	connected: boolean;
	loading: boolean;
}

export function useVehicleUpdates(): UseVehicleUpdatesResult {
	const [vehicleMap, setVehicleMap] = useState<Map<string, VehicleData>>(
		new Map()
	);
	const [connected, setConnected] = useState(false);
	const [loading, setLoading] = useState(true);
	const wsRef = useRef<WebSocket | null>(null);

	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	// Fetch initial vehicle list via REST
	useEffect(() => {
		async function fetchVehicles() {
			try {
				const res = await fetch(`${apiUrl}/vehicles`);
				if (!res.ok) throw new Error(`HTTP ${res.status}`);
				const data = await res.json();
				const vehicles: VehicleData[] = data.vehicles ?? data;
				const map = new Map<string, VehicleData>();
				for (const v of vehicles) {
					map.set(v.id, v);
				}
				setVehicleMap(map);
			} catch (err) {
				console.error("Failed to fetch vehicles:", err);
			} finally {
				setLoading(false);
			}
		}
		fetchVehicles();
	}, [apiUrl]);

	// WebSocket for live position updates
	const handleMessage = useCallback((event: MessageEvent) => {
		try {
			const msg = JSON.parse(event.data);
			if (msg.type !== "vehicle_location") return;

			const { vehicle_id, lat, lon } = msg.data;
			setVehicleMap((prev) => {
				const next = new Map(prev);
				const existing = next.get(vehicle_id);
				if (existing) {
					next.set(vehicle_id, { ...existing, lat, lon });
				} else {
					next.set(vehicle_id, {
						id: vehicle_id,
						lat,
						lon,
						status: "available",
						vehicle_type: "ambulance",
					});
				}
				return next;
			});
		} catch (err) {
			console.error("Error parsing vehicle WS message:", err);
		}
	}, []);

	useEffect(() => {
		const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws";
		const ws = new WebSocket(wsUrl);

		ws.onopen = () => setConnected(true);
		ws.onclose = () => setConnected(false);
		ws.onerror = (err) => console.error("Vehicle WS error:", err);
		ws.onmessage = handleMessage;

		wsRef.current = ws;

		return () => {
			ws.close();
		};
	}, [apiUrl, handleMessage]);

	return {
		vehicles: Array.from(vehicleMap.values()),
		connected,
		loading,
	};
}
