import { useMemo, useRef, useEffect, useState } from "react";
import { GoogleMap, useLoadScript, OverlayView, Polyline, Marker, InfoWindow } from "@react-google-maps/api";
import "./MapPanel.css";
import { AmbulanceMapIcon } from "./AmbulanceMapIcon";
import { UnitInfo } from "./AmbulancePanel";
import { CaseInfo, CasePriority, DispatchSuggestion } from "./types";

interface MapPanelProps {
	units: UnitInfo[];
	focusedUnit: UnitInfo | null;
	routes?: Array<[string, google.maps.LatLngLiteral[]]>;
	incidents?: CaseInfo[];
	dispatchSuggestion?: DispatchSuggestion | null;
	onAcceptSuggestion?: () => void;
	onDeclineSuggestion?: () => void;
}

const PRIORITY_COLORS: Record<CasePriority, string> = {
	Purple: "#884dff",
	Red: "#d6455d",
	Orange: "#e29a00",
	Yellow: "#d4a700",
	Green: "#2e994e",
};

const STATUS_BADGE_STYLES: Record<string, { background: string; color: string }> = {
	open: { background: "#e8f5e9", color: "#2e7d32" },
	in_progress: { background: "#fff3e0", color: "#e65100" },
};

const STATUS_LABELS: Record<string, string> = {
	open: "Open",
	in_progress: "In Progress",
};

function formatTime(iso: string | undefined): string {
	if (!iso) return "";
	return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const parseCoords = (coordString: string) => {
	const [lat, lng] = coordString.split(",").map((s) => parseFloat(s.trim()));
	return { lat, lng };
};

const routePolylineOptions: google.maps.PolylineOptions = {
	strokeColor: "#2563EB",
	strokeOpacity: 0.8,
	strokeWeight: 4,
};

const previewPolylineOptions: google.maps.PolylineOptions = {
	strokeColor: "#e29a00",
	strokeOpacity: 0,
	strokeWeight: 4,
	icons: [
		{
			icon: { path: "M 0,-1 0,1", strokeOpacity: 1, scale: 3 },
			offset: "0",
			repeat: "14px",
		},
	],
};

export default function MapPanel({
	units,
	focusedUnit,
	routes = [],
	incidents = [],
	dispatchSuggestion,
	onAcceptSuggestion,
	onDeclineSuggestion,
}: MapPanelProps) {
	const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
	const { isLoaded } = useLoadScript({ googleMapsApiKey: apiKey! });
	const mapRef = useRef<google.maps.Map | null>(null);
	const defaultCenter = useMemo(() => ({ lat: 43.4643, lng: -80.5205 }), []);
	const [hoveredIncidentId, setHoveredIncidentId] = useState<string | null>(null);

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
				{/* Suggestion InfoWindow on the recommended ambulance */}
				{dispatchSuggestion && (() => {
					const suggestedUnit = units.find(
						(u) => u.id.toLowerCase().replace(/\s+/g, "-") === dispatchSuggestion.vehicleId
					);
					if (!suggestedUnit) return null;
					const pos = parseCoords(suggestedUnit.coords);
					const inc = dispatchSuggestion.incident;
					const priorityColor = PRIORITY_COLORS[inc.priority as CasePriority] ?? "#888";
					return (
						<InfoWindow
							position={pos}
							options={{ pixelOffset: new google.maps.Size(0, -30) }}
							onCloseClick={onDeclineSuggestion}
						>
							<div style={{ fontFamily: "sans-serif", minWidth: 200, padding: "4px 0" }}>
								<div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
									<span style={{
										width: 10, height: 10, borderRadius: "50%",
										backgroundColor: priorityColor,
										display: "inline-block", flexShrink: 0,
									}} />
									<span style={{ fontWeight: 700, fontSize: 14, color: "#222" }}>
										{inc.type}
									</span>
								</div>
								<div style={{ fontSize: 12, fontWeight: 600, color: priorityColor, marginBottom: 4 }}>
									{inc.priority}
								</div>
								<div style={{ fontSize: 12, color: "#555", marginBottom: 8 }}>
									{inc.location}
								</div>
								<div style={{ display: "flex", gap: 8 }}>
									<button
										onClick={onAcceptSuggestion}
										style={{
											flex: 1, padding: "6px 0", border: "none", borderRadius: 6,
											background: "#2e994e", color: "#fff", fontWeight: 600,
											fontSize: 13, cursor: "pointer",
										}}
									>
										Accept
									</button>
									<button
										onClick={onDeclineSuggestion}
										style={{
											flex: 1, padding: "6px 0", border: "none", borderRadius: 6,
											background: "#d6455d", color: "#fff", fontWeight: 600,
											fontSize: 13, cursor: "pointer",
										}}
									>
										Decline
									</button>
								</div>
							</div>
						</InfoWindow>
					);
				})()}

				{/* Preview route polyline (dashed orange) */}
				{dispatchSuggestion && dispatchSuggestion.routePreview.length > 0 && (
					<Polyline
						key="preview-route"
						path={dispatchSuggestion.routePreview}
						options={previewPolylineOptions}
					/>
				)}

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
						icon={{
							path: google.maps.SymbolPath.CIRCLE,
							fillColor: PRIORITY_COLORS[incident.priority] ?? "#888",
							fillOpacity: 1,
							strokeColor: "#fff",
							strokeWeight: 2,
							scale: 10,
						}}
						onMouseOver={() => setHoveredIncidentId(incident.id)}
						onMouseOut={() => setHoveredIncidentId(null)}
					>
						{hoveredIncidentId === incident.id && (
							<InfoWindow>
								<div style={{ fontFamily: "sans-serif", minWidth: 180, padding: "2px 0" }}>
									<div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
										<span style={{
											width: 10, height: 10, borderRadius: "50%",
											backgroundColor: PRIORITY_COLORS[incident.priority] ?? "#888",
											display: "inline-block", flexShrink: 0,
										}} />
										<span style={{ fontWeight: 700, fontSize: 14, color: "#222" }}>
											{incident.type}
										</span>
									</div>
									<div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
										<span style={{
											fontSize: 12, fontWeight: 600,
											color: PRIORITY_COLORS[incident.priority] ?? "#888",
										}}>
											{incident.priority}
										</span>
										<span style={{
											fontSize: 11, fontWeight: 600, borderRadius: 8,
											padding: "2px 8px",
											...(STATUS_BADGE_STYLES[incident.status] ?? {}),
										}}>
											{STATUS_LABELS[incident.status] ?? incident.status}
										</span>
									</div>
									<div style={{ fontSize: 12, color: "#555", marginBottom: 3 }}>
										{incident.location}
									</div>
									<div style={{ fontSize: 11, color: "#888" }}>
										Reported at {formatTime(incident.reported_at)}
									</div>
								</div>
							</InfoWindow>
						)}
					</Marker>
				))}
			</GoogleMap>
		</div>
	);
}
