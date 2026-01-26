import { useMemo, useRef, useEffect } from "react";
import { GoogleMap, useLoadScript, OverlayView } from "@react-google-maps/api";
import "./MapPanel.css";
// IMPORT YOUR NEW COMPONENT
import { AmbulanceMapIcon } from "./AmbulanceMapIcon"; // Adjust path if needed
import { UnitInfo } from "./AmbulancePanel";

interface MapPanelProps {
	units: UnitInfo[];
	focusedUnit: UnitInfo | null;
}

const parseCoords = (coordString: string) => {
	const [lat, lng] = coordString.split(",").map((s) => parseFloat(s.trim()));
	return { lat, lng };
};

export default function MapPanel({ units, focusedUnit }: MapPanelProps) {
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
							{/* We apply the status class to this wrapper */}
							<div
								className={`map-marker-container map-status-${statusClass}`}
							>
								{/* Use the SVG component directly */}
								<AmbulanceMapIcon className="ambulance-svg" />
								<div className="marker-label">{unit.id}</div>
							</div>
						</OverlayView>
					);
				})}
			</GoogleMap>
		</div>
	);
}
