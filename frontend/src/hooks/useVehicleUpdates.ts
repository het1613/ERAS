import { useState, useEffect, useRef, useCallback } from "react";
import { VehicleData } from "../components/AmbulancePanel";

interface UseVehicleUpdatesResult {
	vehicles: VehicleData[];
	routes: Array<[string, google.maps.LatLngLiteral[]]>;
	connected: boolean;
	loading: boolean;
}

export function useVehicleUpdates(): UseVehicleUpdatesResult {
	const [vehicleMap, setVehicleMap] = useState<Map<string, VehicleData>>(
		new Map()
	);
	const [routeMap, setRouteMap] = useState<
		Map<string, google.maps.LatLngLiteral[]>
	>(new Map());
	// Track which incident corresponds to which vehicle for cleanup
	const incidentToVehicleRef = useRef<Map<string, string>>(new Map());
	const [connected, setConnected] = useState(false);
	const [loading, setLoading] = useState(true);
	const wsRef = useRef<WebSocket | null>(null);

	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	// Fetch initial vehicle list + active routes via REST
	useEffect(() => {
		async function fetchInitialState() {
			try {
				const [vehiclesRes, routesRes] = await Promise.all([
					fetch(`${apiUrl}/vehicles`),
					fetch(`${apiUrl}/active-routes`),
				]);

				if (vehiclesRes.ok) {
					const data = await vehiclesRes.json();
					const vehicles: VehicleData[] = data.vehicles ?? data;
					const map = new Map<string, VehicleData>();
					for (const v of vehicles) {
						map.set(v.id, v);
					}
					setVehicleMap(map);
				}

				if (routesRes.ok) {
					const data = await routesRes.json();
					// data.routes is { vehicle_id: { incident_id, route: [{lat,lng},...] } }
					const routes: Record<string, { incident_id: string; route: google.maps.LatLngLiteral[] }> = data.routes ?? {};
					const rMap = new Map<string, google.maps.LatLngLiteral[]>();
					for (const [vehicleId, entry] of Object.entries(routes)) {
						if (entry.route && entry.route.length > 0) {
							rMap.set(vehicleId, entry.route);
							incidentToVehicleRef.current.set(entry.incident_id, vehicleId);
						}
					}
					setRouteMap(rMap);
				}
			} catch (err) {
				console.error("Failed to fetch initial state:", err);
			} finally {
				setLoading(false);
			}
		}
		fetchInitialState();
	}, [apiUrl]);

	// WebSocket for live updates
	const handleMessage = useCallback((event: MessageEvent) => {
		try {
			const msg = JSON.parse(event.data);

			if (msg.type === "vehicle_location") {
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
			} else if (msg.type === "vehicle_dispatched") {
				const { vehicle_id, incident_id, route } = msg.data;
				if (route && route.length > 0) {
					setRouteMap((prev) => {
						const next = new Map(prev);
						next.set(vehicle_id, route);
						return next;
					});
					incidentToVehicleRef.current.set(incident_id, vehicle_id);
				}
			} else if (msg.type === "incident_updated") {
				const incident = msg.data;
				if (incident.status === "resolved") {
					const vehicleId = incidentToVehicleRef.current.get(
						incident.id
					);
					if (vehicleId) {
						setRouteMap((prev) => {
							const next = new Map(prev);
							next.delete(vehicleId);
							return next;
						});
						incidentToVehicleRef.current.delete(incident.id);
					}
				}
			}
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
		routes: Array.from(routeMap.entries()),
		connected,
		loading,
	};
}
