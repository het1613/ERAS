import { useMemo, useRef, useEffect } from "react";
import { GoogleMap, useLoadScript, OverlayView, Polyline, Marker } from "@react-google-maps/api";
import "./MapPanel.css";
import { AmbulanceMapIcon } from "./AmbulanceMapIcon";
import { UnitInfo } from "./AmbulancePanel";
import { CaseInfo, CasePriority } from "./types";

interface MapPanelProps {
	units: UnitInfo[];
	focusedUnit: UnitInfo | null;
	routes?: Array<[string, google.maps.LatLngLiteral[]]>;
	incidents?: CaseInfo[];
}

const PRIORITY_COLORS: Record<CasePriority, string> = {
	Purple: "#884dff",
	Red: "#d6455d",
	Orange: "#e29a00",
	Yellow: "#d4a700",
	Green: "#2e994e",
};

const parseCoords = (coordString: string) => {
	const [lat, lng] = coordString.split(",").map((s) => parseFloat(s.trim()));
	return { lat, lng };
};

const routePolylineOptions: google.maps.PolylineOptions = {
	strokeColor: "#2563EB",
	strokeOpacity: 0.8,
	strokeWeight: 4,
};

export default function MapPanel({ units, focusedUnit, routes = [], incidents = [] }: MapPanelProps) {
	const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
	const { isLoaded } = useLoadScript({ googleMapsApiKey: apiKey! });
	const mapRef = useRef<google.maps.Map | null>(null);
	const defaultCenter = useMemo(() => ({ lat: 43.4643, lng: -80.5205 }), []);

	useEffect(() => {
		if (focusedUnit && mapRef.current) {
			const position = parseCoords(focusedUnit.coords);
			mapRef.current.panTo(position);
			mapRef.current.setZoom(15);
		}
	}, [focusedUnit]);

	if (!isLoaded) return <div>Loading Map...</div>;

	return (
		<div style={{ height: "100vh", width: "100vw" }}>
			<GoogleMap
				zoom={12}
				center={defaultCenter}
				onLoad={(map) => {
					mapRef.current = map;
				}}
				mapContainerStyle={{ width: "100%", height: "100%" }}
			>
				{units.map((unit) => {
					const position = parseCoords(unit.coords);
					const statusClass = unit.status
						.toLowerCase()
						.replace("on-scene", "onscene");

					return (
						<OverlayView
							key={unit.id}
							position={position}
							mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}
						>
							<div
								className={`map-marker-container map-status-${statusClass}`}
							>
								<AmbulanceMapIcon className="ambulance-svg" />
								<div className="marker-label">{unit.id}</div>
							</div>
						</OverlayView>
					);
				})}
				{routes.map(([vehicleId, path]) => (
					<Polyline
						key={`route-${vehicleId}`}
						path={path}
						options={routePolylineOptions}
					/>
				))}
				{incidents.map((incident) => (
					<Marker
						key={`incident-${incident.id}`}
						position={{ lat: incident.lat, lng: incident.lon }}
						title={incident.type}
						icon={{
							path: google.maps.SymbolPath.CIRCLE,
							fillColor: PRIORITY_COLORS[incident.priority] ?? "#888",
							fillOpacity: 1,
							strokeColor: "#fff",
							strokeWeight: 2,
							scale: 10,
						}}
					/>
				))}
			</GoogleMap>
		</div>
	);
}
