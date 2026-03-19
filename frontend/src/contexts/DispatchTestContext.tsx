import {
	createContext,
	useContext,
	useState,
	useCallback,
	useEffect,
	useRef,
	ReactNode,
} from "react";
import { useWebSocket } from "./WebSocketContext";

interface TestIncident {
	incidentId: string;
	priority: string;
	type: string;
	location: string;
	createdAt: number;
	dispatchedAt: number | null;
}

type TestPhase = "idle" | "resetting" | "running" | "waiting" | "complete";

interface DispatchTestContextValue {
	phase: TestPhase;
	incidents: TestIncident[];
	createdCount: number;
	dispatchedCount: number;
	manualMode: boolean;
	toggleManualMode: () => void;
	startTest: () => void;
	confirmConsent: () => void;
	cancelConsent: () => void;
	consentModalOpen: boolean;
	dismissResults: () => void;
}

const DispatchTestContext = createContext<DispatchTestContextValue | null>(null);

const TEST_INCIDENTS = [
	{
		priority: "Purple",
		type: "Cardiac Arrest",
		location: "25 Gaukel St, Kitchener",
		lat: 43.4512,
		lon: -80.4918,
	},
	{
		priority: "Orange",
		type: "Seizure",
		location: "450 Columbia St W, Waterloo",
		lat: 43.469,
		lon: -80.55,
	},
	{
		priority: "Yellow",
		type: "Breathing Difficulty",
		location: "385 Fairway Rd S, Kitchener",
		lat: 43.43,
		lon: -80.47,
	},
	{
		priority: "Red",
		type: "Chest Pain",
		location: "73 Water St N, Cambridge",
		lat: 43.365,
		lon: -80.317,
	},
	{
		priority: "Orange",
		type: "Motor Vehicle Accident",
		location: "Homer Watson Blvd, Kitchener",
		lat: 43.41,
		lon: -80.45,
	},
	{
		priority: "Yellow",
		type: "Suspected Stroke",
		location: "15 King St N, Waterloo",
		lat: 43.465,
		lon: -80.524,
	},
];

const TOTAL_INCIDENTS = TEST_INCIDENTS.length;
const CREATE_INTERVAL_MS = 10_000;
const TIMEOUT_MS = 120_000;

export function DispatchTestProvider({ children }: { children: ReactNode }) {
	const [phase, setPhase] = useState<TestPhase>("idle");
	const [incidents, setIncidents] = useState<TestIncident[]>([]);
	const [manualMode, setManualMode] = useState(false);
	const [consentModalOpen, setConsentModalOpen] = useState(false);
	const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const createIndexRef = useRef(0);
	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	const { subscribe } = useWebSocket();

	// Track dispatch completions via WebSocket
	useEffect(() => {
		return subscribe((msg) => {
			if (
				msg.type === "incident_updated" &&
				msg.data?.status === "dispatched"
			) {
				const incidentId = msg.data.id;
				setIncidents((prev) => {
					const idx = prev.findIndex(
						(t) => t.incidentId === incidentId && t.dispatchedAt === null
					);
					if (idx === -1) return prev;
					const updated = [...prev];
					updated[idx] = { ...updated[idx], dispatchedAt: Date.now() };
					return updated;
				});
			}
		});
	}, [subscribe]);

	// Check for completion: all incidents created AND all dispatched
	useEffect(() => {
		if (phase !== "running" && phase !== "waiting") return;
		const allCreated = incidents.length === TOTAL_INCIDENTS;
		const allDispatched =
			allCreated && incidents.every((t) => t.dispatchedAt !== null);
		if (allDispatched) {
			setPhase("complete");
		} else if (allCreated && phase === "running") {
			setPhase("waiting");
		}
	}, [phase, incidents]);

	// Cleanup timers on phase change to idle/complete
	useEffect(() => {
		if (phase === "complete" || phase === "idle") {
			if (intervalRef.current) {
				clearInterval(intervalRef.current);
				intervalRef.current = null;
			}
			if (timeoutRef.current) {
				clearTimeout(timeoutRef.current);
				timeoutRef.current = null;
			}
		}
	}, [phase]);

	const createNextIncident = useCallback(async () => {
		const idx = createIndexRef.current;
		if (idx >= TOTAL_INCIDENTS) {
			if (intervalRef.current) {
				clearInterval(intervalRef.current);
				intervalRef.current = null;
			}
			return;
		}

		const inc = TEST_INCIDENTS[idx];
		createIndexRef.current = idx + 1;

		try {
			const res = await fetch(`${apiUrl}/incidents`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					lat: inc.lat,
					lon: inc.lon,
					location: inc.location,
					type: inc.type,
					priority: inc.priority,
					source: "call_taker",
				}),
			});
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			const incidentId = data.incident?.id || data.id;

			setIncidents((prev) => [
				...prev,
				{
					incidentId,
					priority: inc.priority,
					type: inc.type,
					location: inc.location,
					createdAt: Date.now(),
					dispatchedAt: null,
				},
			]);
		} catch (err) {
			console.error("Failed to create test incident:", err);
		}
	}, [apiUrl]);

	const startTest = useCallback(() => {
		if (phase !== "idle") return;
		setConsentModalOpen(true);
	}, [phase]);

	const confirmConsent = useCallback(async () => {
		// Reset phase
		setPhase("resetting");
		setIncidents([]);
		createIndexRef.current = 0;

		try {
			const res = await fetch(`${apiUrl}/admin/reset`, { method: "POST" });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
		} catch (err) {
			console.error("Reset failed:", err);
			alert("Failed to reset system.");
			setPhase("idle");
			setConsentModalOpen(false);
			return;
		}

		setConsentModalOpen(false);
		setPhase("running");

		// Create first incident immediately, then every 10s
		createNextIncident();
		intervalRef.current = setInterval(createNextIncident, CREATE_INTERVAL_MS);

		// 2 minute timeout fallback
		timeoutRef.current = setTimeout(() => {
			setPhase((p) => {
				if (p === "running" || p === "waiting") return "complete";
				return p;
			});
		}, TIMEOUT_MS);
	}, [apiUrl, createNextIncident]);

	const cancelConsent = useCallback(() => {
		setConsentModalOpen(false);
	}, []);

	const dismissResults = useCallback(() => {
		setPhase("idle");
		setIncidents([]);
		createIndexRef.current = 0;
	}, []);

	const toggleManualMode = useCallback(() => {
		setManualMode((prev) => !prev);
	}, []);

	const createdCount = incidents.length;
	const dispatchedCount = incidents.filter((t) => t.dispatchedAt !== null).length;

	return (
		<DispatchTestContext.Provider
			value={{
				phase,
				incidents,
				createdCount,
				dispatchedCount,
				manualMode,
				toggleManualMode,
				startTest,
				confirmConsent,
				cancelConsent,
				consentModalOpen,
				dismissResults,
			}}
		>
			{children}
		</DispatchTestContext.Provider>
	);
}

export function useDispatchTest() {
	const ctx = useContext(DispatchTestContext);
	if (!ctx)
		throw new Error("useDispatchTest must be used within DispatchTestProvider");
	return ctx;
}
