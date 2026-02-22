import React, { useMemo, useRef, useEffect } from "react";
import { GoogleMap, useLoadScript, OverlayView } from "@react-google-maps/api";
import "./MapPanel.css";
import { AmbulanceMapIcon } from "./AmbulanceMapIcon";
import { IncidentMapIcon } from "./IncidentMapIcon";
import { UnitInfo } from "./AmbulancePanel";
import { CaseInfo } from "./types";

const getPriorityColor = (p: string) => {
	switch (p) {
		case "Purple":
			return "#884dff";
		case "Red":
			return "#d6455d";
		case "Orange":
			return "#e29a00";
		case "Yellow":
			return "#d4a700";
		case "Green":
			return "#2e994e";
		default:
			return "#000";
	}
};

interface MapPanelProps {
	units: UnitInfo[];
	focusedUnit: UnitInfo | null;
	cases?: CaseInfo[];
}

const parseCoords = (coordString: string) => {
	const [lat, lng] = coordString.split(",").map((s) => parseFloat(s.trim()));
	return { lat, lng };
};

export default function MapPanel({ units, focusedUnit, cases = [] }: MapPanelProps) {
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
							</div>
						</OverlayView>
					);
				})}
				{cases
					.filter((c) => c.lat != null && c.lng != null)
					.map((c) => (
						<OverlayView
							key={c.id}
							position={{ lat: c.lat!, lng: c.lng! }}
							mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}
						>
							<div className="map-marker-container">
								<IncidentMapIcon
									className="incident-svg"
									color={getPriorityColor(c.priority)}
								/>
							</div>
						</OverlayView>
					))}
			</GoogleMap>
		</div>
	);
}
