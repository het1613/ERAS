import { useMemo, useRef, useEffect, useState } from "react";
import {
	GoogleMap,
	useLoadScript,
	OverlayView,
	Marker,
	Polyline,
	InfoWindow,
} from "@react-google-maps/api";
import "./MapPanel.css";
import { IncidentMapIcon } from "./IncidentMapIcon";
import { UnitInfo, UnitStatus } from "./AmbulancePanel";
import { CaseInfo, CasePriority, DispatchSuggestion } from "./types";

const GRAND_RIVER_HOSPITAL = {
	lat: 43.455280,
	lng: -80.505836,
	name: "Grand River Hospital",
	address: "835 King St W, Kitchener",
};

const RAW_PRIORITY_COLORS: Record<CasePriority, string> = {
	Purple: "#7c3aed",
	Red: "#dc2626",
	Orange: "#ea580c",
	Yellow: "#ca8a04",
	Green: "#16a34a",
};

const STATUS_MARKER_COLORS: Record<UnitStatus, string> = {
	Available: "#16a34a",
	Dispatched: "#d97706",
	"On-scene": "#dc2626",
	Returning: "#2563eb",
};

const AMBULANCE_PATH = "M25.7955 24.2222H24.6591V23.1111C24.6591 22.8164 24.5394 22.5338 24.3263 22.3254C24.1131 22.1171 23.8241 22 23.5227 22C23.2213 22 22.9323 22.1171 22.7192 22.3254C22.5061 22.5338 22.3864 22.8164 22.3864 23.1111V24.2222H21.25C20.9486 24.2222 20.6596 24.3393 20.4465 24.5477C20.2334 24.756 20.1136 25.0386 20.1136 25.3333C20.1136 25.628 20.2334 25.9106 20.4465 26.119C20.6596 26.3274 20.9486 26.4444 21.25 26.4444H22.3864V27.5556C22.3864 27.8502 22.5061 28.1329 22.7192 28.3412C22.9323 28.5496 23.2213 28.6667 23.5227 28.6667C23.8241 28.6667 24.1131 28.5496 24.3263 28.3412C24.5394 28.1329 24.6591 27.8502 24.6591 27.5556V26.4444H25.7955C26.0968 26.4444 26.3859 26.3274 26.599 26.119C26.8121 25.9106 26.9318 25.628 26.9318 25.3333C26.9318 25.0386 26.8121 24.756 26.599 24.5477C26.3859 24.3393 26.0968 24.2222 25.7955 24.2222ZM39.9205 26.6111L39.8523 26.4889C39.8327 26.4339 39.806 26.3816 39.7727 26.3333L37.0455 22.7778C36.7279 22.3638 36.3161 22.0278 35.8428 21.7964C35.3694 21.5649 34.8474 21.4444 34.3182 21.4444H32.0455V20.3333C32.0455 19.4493 31.6863 18.6014 31.047 17.9763C30.4076 17.3512 29.5405 17 28.6364 17H18.4091C17.5049 17 16.6378 17.3512 15.9985 17.9763C15.3592 18.6014 15 19.4493 15 20.3333V32.5556C15 32.8502 15.1197 33.1329 15.3328 33.3412C15.5459 33.5496 15.835 33.6667 16.1364 33.6667H17.2727C17.2727 34.5507 17.6319 35.3986 18.2712 36.0237C18.9106 36.6488 19.7777 37 20.6818 37C21.586 37 22.4531 36.6488 23.0924 36.0237C23.7317 35.3986 24.0909 34.5507 24.0909 33.6667H30.9091C30.9091 34.5507 31.2683 35.3986 31.9076 36.0237C32.5469 36.6488 33.414 37 34.3182 37C35.2223 37 36.0894 36.6488 36.7288 36.0237C37.3681 35.3986 37.7273 34.5507 37.7273 33.6667H38.8636C39.165 33.6667 39.4541 33.5496 39.6672 33.3412C39.8803 33.1329 40 32.8502 40 32.5556V27C39.9976 26.8668 39.9706 26.735 39.9205 26.6111ZM20.6818 34.7778C20.4571 34.7778 20.2374 34.7126 20.0505 34.5905C19.8636 34.4684 19.718 34.2949 19.632 34.0919C19.5459 33.8888 19.5234 33.6654 19.5673 33.4499C19.6111 33.2344 19.7194 33.0364 19.8783 32.881C20.0372 32.7256 20.2397 32.6198 20.4601 32.5769C20.6806 32.534 20.909 32.556 21.1167 32.6401C21.3243 32.7242 21.5018 32.8666 21.6267 33.0494C21.7515 33.2321 21.8182 33.4469 21.8182 33.6667C21.8182 33.9614 21.6985 34.244 21.4853 34.4523C21.2722 34.6607 20.9832 34.7778 20.6818 34.7778ZM29.7727 31.4444H23.2045C22.885 31.1007 22.4956 30.8261 22.0611 30.6381C21.6267 30.4502 21.1569 30.3531 20.6818 30.3531C20.2068 30.3531 19.737 30.4502 19.3025 30.6381C18.8681 30.8261 18.4786 31.1007 18.1591 31.4444H17.2727V20.3333C17.2727 20.0386 17.3925 19.756 17.6056 19.5477C17.8187 19.3393 18.1077 19.2222 18.4091 19.2222H28.6364C28.9377 19.2222 29.2268 19.3393 29.4399 19.5477C29.653 19.756 29.7727 20.0386 29.7727 20.3333V31.4444ZM32.0455 23.6667H34.3182C34.4946 23.6667 34.6686 23.7068 34.8264 23.784C34.9842 23.8611 35.1214 23.9731 35.2273 24.1111L36.5909 25.8889H32.0455V23.6667ZM34.3182 34.7778C34.0934 34.7778 33.8737 34.7126 33.6869 34.5905C33.5 34.4684 33.3543 34.2949 33.2683 34.0919C33.1823 33.8888 33.1598 33.6654 33.2037 33.4499C33.2475 33.2344 33.3557 33.0364 33.5147 32.881C33.6736 32.7256 33.8761 32.6198 34.0965 32.5769C34.3169 32.534 34.5454 32.556 34.753 32.6401C34.9607 32.7242 35.1382 32.8666 35.263 33.0494C35.3879 33.2321 35.4545 33.4469 35.4545 33.6667C35.4545 33.9614 35.3348 34.244 35.1217 34.4523C34.9086 34.6607 34.6196 34.7778 34.3182 34.7778ZM37.7273 31.4444H36.8409C36.2362 30.7934 35.3929 30.4024 34.4947 30.3566C33.5964 30.3108 32.7161 30.614 32.0455 31.2V28.1111H37.7273V31.4444Z";

function makeAmbulanceSvgUrl(color: string): string {
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="54" height="54" viewBox="0 0 54 54" fill="none"><circle opacity="0.3" cx="27" cy="27" r="27" fill="${color}"/><circle cx="27" cy="27" r="21" fill="${color}" stroke="white" stroke-width="2"/><path d="${AMBULANCE_PATH}" fill="white"/></svg>`;
	return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

const ambulanceIconCache = new Map<string, google.maps.Icon>();
function getAmbulanceIcon(color: string): google.maps.Icon {
	let icon = ambulanceIconCache.get(color);
	if (!icon) {
		icon = {
			url: makeAmbulanceSvgUrl(color),
			scaledSize: new google.maps.Size(36, 36),
			anchor: new google.maps.Point(18, 18),
		};
		ambulanceIconCache.set(color, icon);
	}
	return icon;
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
	strokeColor: "#ea580c",
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

interface MapPanelProps {
	units: UnitInfo[];
	focusedUnit: UnitInfo | null;
	routes?: Array<[string, google.maps.LatLngLiteral[]]>;
	incidents?: CaseInfo[];
	dispatchSuggestion?: DispatchSuggestion | null;
	onAcceptSuggestion?: () => void;
	onDeclineSuggestion?: () => void;
}

function formatVehicleLabel(id: string) {
	return id.replace(/[-_]/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
}

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
	const [hoveredHospital, setHoveredHospital] = useState(false);

	useEffect(() => {
		if (focusedUnit && mapRef.current) {
			const position = parseCoords(focusedUnit.coords);
			mapRef.current.panTo(position);
			mapRef.current.setZoom(15);
		}
	}, [focusedUnit]);

	if (!isLoaded) {
		return (
			<div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", width: "100%", color: "var(--text-tertiary)" }}>
				Loading Map...
			</div>
		);
	}

	return (
		<div style={{ position: "absolute", inset: 0 }}>
			<GoogleMap
				zoom={12}
				center={defaultCenter}
				onLoad={(map) => { mapRef.current = map; }}
				mapContainerStyle={{ width: "100%", height: "100%" }}
				options={{
					disableDefaultUI: false,
					zoomControl: true,
					mapTypeControl: false,
					streetViewControl: false,
					fullscreenControl: false,
					styles: [
						{ featureType: "poi", stylers: [{ visibility: "off" }] },
						{ featureType: "transit", stylers: [{ visibility: "off" }] },
					],
				}}
			>
			{/* Ambulance Markers */}
			{units.map((unit) => {
				const position = parseCoords(unit.coords);
				if (isNaN(position.lat) || isNaN(position.lng)) return null;
				const color = STATUS_MARKER_COLORS[unit.status] ?? "#16a34a";

				return (
					<Marker
						key={unit.id}
						position={position}
						icon={getAmbulanceIcon(color)}
						title={`${unit.id} - ${unit.status}`}
					/>
				);
			})}

				{/* Dispatch Suggestion InfoWindow */}
				{dispatchSuggestion && (() => {
					const suggestedUnit = units.find(
						(u) => u.id.toLowerCase().replace(/\s+/g, "-") === dispatchSuggestion.vehicleId,
					);
					if (!suggestedUnit) return null;
					const pos = parseCoords(suggestedUnit.coords);
					const inc = dispatchSuggestion.incident;
					const priorityColor = RAW_PRIORITY_COLORS[inc.priority as CasePriority] ?? "#888";
					const vehicleLabel = formatVehicleLabel(dispatchSuggestion.vehicleId);

					return (
						<InfoWindow position={pos} options={{ pixelOffset: new google.maps.Size(0, -30) }} onCloseClick={onDeclineSuggestion}>
							<div className="map-iw">
								<div className="map-iw-label">Dispatch Suggestion</div>
								<div className="map-iw-vehicle">{vehicleLabel}</div>
								<div className="map-iw-incident">
									<span className="map-iw-dot" style={{ backgroundColor: priorityColor }} />
									<span className="map-iw-type">{inc.type}</span>
								</div>
								<div className="map-iw-priority" style={{ color: priorityColor }}>{inc.priority} Priority</div>
								<div className="map-iw-location">{inc.location}</div>
								<div className="map-iw-actions">
									<button className="map-iw-btn map-iw-btn-accept" onClick={onAcceptSuggestion}>Accept</button>
									<button className="map-iw-btn map-iw-btn-another" onClick={onDeclineSuggestion}>Suggest Another</button>
								</div>
							</div>
						</InfoWindow>
					);
				})()}

				{/* Preview route (dashed orange) */}
				{dispatchSuggestion && dispatchSuggestion.routePreview.length > 0 && (
					<Polyline key="preview-route" path={dispatchSuggestion.routePreview} options={previewPolylineOptions} />
				)}

				{/* Active routes (solid blue) */}
				{routes.map(([vehicleId, path]) => (
					<Polyline key={`route-${vehicleId}`} path={path} options={routePolylineOptions} />
				))}

				{/* Incident Markers */}
				{incidents.map((incident) => (
					<OverlayView
						key={`incident-${incident.id}`}
						position={{ lat: incident.lat, lng: incident.lon }}
						mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}
					>
						<div
							className="map-marker-container"
							onMouseEnter={() => setHoveredIncidentId(incident.id)}
							onMouseLeave={() => setHoveredIncidentId(null)}
							style={{ position: "relative" }}
						>
							<IncidentMapIcon className="incident-svg" color={RAW_PRIORITY_COLORS[incident.priority] ?? "#888"} />
							{hoveredIncidentId === incident.id && (
								<div className="map-incident-tooltip">
									<div className="map-it-header">
										<span className="map-it-dot" style={{ backgroundColor: RAW_PRIORITY_COLORS[incident.priority] ?? "#888" }} />
										<span className="map-it-type">{incident.type}</span>
									</div>
									<div className="map-it-meta">
										<span className="map-it-priority" style={{ color: RAW_PRIORITY_COLORS[incident.priority] ?? "#888" }}>
											{incident.priority}
										</span>
										<span className="map-it-status">{incident.status.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
									</div>
									<div className="map-it-location">{incident.location}</div>
								</div>
							)}
						</div>
					</OverlayView>
				))}

				{/* Hospital Marker */}
				<OverlayView
					position={GRAND_RIVER_HOSPITAL}
					mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}
				>
					<div
						className="map-marker-container"
						onMouseEnter={() => setHoveredHospital(true)}
						onMouseLeave={() => setHoveredHospital(false)}
						style={{ position: "relative" }}
					>
						<div className="map-hospital-icon">
							<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
								<rect width="28" height="28" rx="6" fill="#dc2626"/>
								<rect x="2" y="2" width="24" height="24" rx="5" fill="white" stroke="#dc2626" strokeWidth="1.5"/>
								<path d="M15.5 8H12.5V12.5H8V15.5H12.5V20H15.5V15.5H20V12.5H15.5V8Z" fill="#dc2626"/>
							</svg>
						</div>
						{hoveredHospital && (
							<div className="map-incident-tooltip">
								<div className="map-it-header">
									<span className="map-it-dot" style={{ backgroundColor: "#dc2626" }} />
									<span className="map-it-type">{GRAND_RIVER_HOSPITAL.name}</span>
								</div>
								<div className="map-it-location">{GRAND_RIVER_HOSPITAL.address}</div>
							</div>
						)}
					</div>
				</OverlayView>
			</GoogleMap>
		</div>
	);
}
