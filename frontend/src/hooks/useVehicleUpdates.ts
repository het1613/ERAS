import { useState, useEffect, useCallback, useRef } from "react";
import { VehicleData } from "../components/AmbulancePanel";
import { useWebSocket } from "../contexts/WebSocketContext";

interface UseVehicleUpdatesResult {
	vehicles: VehicleData[];
	routes: Array<[string, google.maps.LatLngLiteral[]]>;
	incidentVehicleMap: Record<string, string>;
	connected: boolean;
	loading: boolean;
}

function trimRouteToVehicle(
	route: google.maps.LatLngLiteral[],
	vehicleLat: number,
	vehicleLng: number
): google.maps.LatLngLiteral[] {
	if (route.length < 2) return route;
	let closestIdx = 0;
	let closestDist = Infinity;
	for (let i = 0; i < route.length; i++) {
		const d =
			(route[i].lat - vehicleLat) ** 2 + (route[i].lng - vehicleLng) ** 2;
		if (d < closestDist) {
			closestDist = d;
			closestIdx = i;
		}
	}
	const remaining = route.slice(closestIdx + 1);
	if (remaining.length === 0) return [];
	return [{ lat: vehicleLat, lng: vehicleLng }, ...remaining];
}

export function useVehicleUpdates(): UseVehicleUpdatesResult {
	const [vehicleMap, setVehicleMap] = useState<Map<string, VehicleData>>(
		new Map()
	);
	const [routeMap, setRouteMap] = useState<
		Map<string, google.maps.LatLngLiteral[]>
	>(new Map());
	const fullRouteMap = useRef<Map<string, google.maps.LatLngLiteral[]>>(
		new Map()
	);
	const [incidentVehicleMap, setIncidentVehicleMap] = useState<
		Record<string, string>
	>({});
	const [loading, setLoading] = useState(true);

	const { connected, subscribe } = useWebSocket();
	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
					const routes: Record<
						string,
						{ incident_id: string; route: google.maps.LatLngLiteral[] }
					> = data.routes ?? {};
					const rMap = new Map<string, google.maps.LatLngLiteral[]>();
					const ivMap: Record<string, string> = {};
					for (const [vehicleId, entry] of Object.entries(routes)) {
						if (entry.route && entry.route.length > 0) {
							rMap.set(vehicleId, entry.route);
							fullRouteMap.current.set(vehicleId, [...entry.route]);
							ivMap[entry.incident_id] = vehicleId;
						}
					}
					setRouteMap(rMap);
					setIncidentVehicleMap(ivMap);
				}
			} catch (err) {
				console.error("Failed to fetch initial state:", err);
			} finally {
				setLoading(false);
			}
		}
		fetchInitialState();
	}, [apiUrl]);

	const handleMessage = useCallback(
		(msg: { type: string; data: any }) => {
			if (msg.type === "vehicle_location") {
				const { vehicle_id, lat, lon, status } = msg.data;
				setVehicleMap((prev) => {
					const next = new Map(prev);
					const existing = next.get(vehicle_id);
					if (existing) {
						next.set(vehicle_id, {
							...existing,
							lat,
							lon,
							status: status ?? existing.status,
						});
					} else {
						next.set(vehicle_id, {
							id: vehicle_id,
							lat,
							lon,
							status: status ?? "available",
							vehicle_type: "ambulance",
						});
					}
					return next;
				});

				// Trim route to show only remaining path ahead of vehicle
				setRouteMap((prev) => {
					const currentRoute = prev.get(vehicle_id);
					if (!currentRoute || currentRoute.length === 0) return prev;
					const trimmed = trimRouteToVehicle(currentRoute, lat, lon);
					if (trimmed.length === 0) {
						const next = new Map(prev);
						next.delete(vehicle_id);
						fullRouteMap.current.delete(vehicle_id);
						return next;
					}
					const next = new Map(prev);
					next.set(vehicle_id, trimmed);
					return next;
				});
			} else if (msg.type === "vehicle_dispatched") {
				const { vehicle_id, incident_id, route } = msg.data;
				if (route && route.length > 0) {
					fullRouteMap.current.set(vehicle_id, [...route]);
					setRouteMap((prev) => {
						const next = new Map(prev);
						next.set(vehicle_id, route);
						return next;
					});
					setIncidentVehicleMap((prev) => ({
						...prev,
						[incident_id]: vehicle_id,
					}));
				}
			} else if (msg.type === "incident_updated") {
				const incident = msg.data;
				if (incident.status === "resolved") {
					setIncidentVehicleMap((prev) => {
						const vehicleId = prev[incident.id];
						if (vehicleId) {
							setRouteMap((rPrev) => {
								const next = new Map(rPrev);
								next.delete(vehicleId);
								return next;
							});
							fullRouteMap.current.delete(vehicleId);
							const { [incident.id]: _, ...rest } = prev;
							return rest;
						}
						return prev;
					});
				}
			}
		},
		[]
	);

	useEffect(() => {
		return subscribe(handleMessage);
	}, [subscribe, handleMessage]);

	return {
		vehicles: Array.from(vehicleMap.values()),
		routes: Array.from(routeMap.entries()),
		incidentVehicleMap,
		connected,
		loading,
	};
}
