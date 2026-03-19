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

export interface TlxScores {
	mentalDemand: number;
	physicalDemand: number;
	temporalDemand: number;
	effort: number;
	performance: number;
	frustration: number;
}

type TestPhase =
	| "idle"
	| "resetting"
	| "round_running"
	| "round_waiting"
	| "tlx"
	| "complete";

type RoundMode = "manual" | "optimizer";

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
	// A/B test state
	currentRound: number;
	roundOrder: RoundMode[];
	testLocked: boolean;
	submitTlx: (scores: TlxScores) => void;
	submitFeedback: (feedback: string) => void;
	round1Incidents: TestIncident[];
	round2Incidents: TestIncident[];
	round1TlxScores: TlxScores | null;
	round2TlxScores: TlxScores | null;
	studyId: string | null;
}

const DispatchTestContext = createContext<DispatchTestContextValue | null>(null);

// Round 1 incidents: 1 Purple, 1 Red, 2 Orange, 2 Yellow
const ROUND_1_INCIDENTS = [
	{
		priority: "Purple",
		type: "Cardiac Arrest",
		location: "25 Gaukel St, Kitchener",
		lat: 43.4512,
		lon: -80.4918,
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
		type: "Seizure",
		location: "450 Columbia St W, Waterloo",
		lat: 43.469,
		lon: -80.55,
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
		type: "Breathing Difficulty",
		location: "385 Fairway Rd S, Kitchener",
		lat: 43.43,
		lon: -80.47,
	},
	{
		priority: "Yellow",
		type: "Suspected Stroke",
		location: "15 King St N, Waterloo",
		lat: 43.465,
		lon: -80.524,
	},
];

// Round 2 incidents: same priority distribution, different locations/types
const ROUND_2_INCIDENTS = [
	{
		priority: "Purple",
		type: "Drowning",
		location: "101 Queen St S, Kitchener",
		lat: 43.448,
		lon: -80.494,
	},
	{
		priority: "Red",
		type: "Severe Allergic Reaction",
		location: "200 University Ave W, Waterloo",
		lat: 43.473,
		lon: -80.535,
	},
	{
		priority: "Orange",
		type: "Fall with Injury",
		location: "1400 Weber St E, Kitchener",
		lat: 43.442,
		lon: -80.455,
	},
	{
		priority: "Orange",
		type: "Bicycle Collision",
		location: "120 Main St, Cambridge",
		lat: 43.358,
		lon: -80.313,
	},
	{
		priority: "Yellow",
		type: "Abdominal Pain",
		location: "500 Hespeler Rd, Cambridge",
		lat: 43.395,
		lon: -80.365,
	},
	{
		priority: "Yellow",
		type: "Laceration",
		location: "50 Westmount Rd N, Waterloo",
		lat: 43.475,
		lon: -80.545,
	},
];

const TOTAL_INCIDENTS = 6;
const CREATE_INTERVAL_MS = 10_000;
const TIMEOUT_MS = 120_000;

export function DispatchTestProvider({ children }: { children: ReactNode }) {
	const [phase, setPhase] = useState<TestPhase>("idle");
	const [incidents, setIncidents] = useState<TestIncident[]>([]);
	const [manualMode, setManualMode] = useState(false);
	const [consentModalOpen, setConsentModalOpen] = useState(false);

	// A/B test state
	const [studyId, setStudyId] = useState<string | null>(null);
	const [currentRound, setCurrentRound] = useState(1);
	const [roundOrder, setRoundOrder] = useState<RoundMode[]>(["manual", "optimizer"]);
	const [testLocked, setTestLocked] = useState(false);
	const [round1Incidents, setRound1Incidents] = useState<TestIncident[]>([]);
	const [round2Incidents, setRound2Incidents] = useState<TestIncident[]>([]);
	const [round1TlxScores, setRound1TlxScores] = useState<TlxScores | null>(null);
	const [round2TlxScores, setRound2TlxScores] = useState<TlxScores | null>(null);

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

	// Check for round completion: all incidents created AND all dispatched
	useEffect(() => {
		if (phase !== "round_running" && phase !== "round_waiting") return;
		const allCreated = incidents.length === TOTAL_INCIDENTS;
		const allDispatched =
			allCreated && incidents.every((t) => t.dispatchedAt !== null);
		if (allDispatched) {
			setPhase("tlx");
		} else if (allCreated && phase === "round_running") {
			setPhase("round_waiting");
		}
	}, [phase, incidents]);

	// Cleanup timers on phase change to idle/complete/tlx
	useEffect(() => {
		if (phase === "complete" || phase === "idle" || phase === "tlx") {
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

	const getIncidentsForRound = useCallback((round: number) => {
		return round === 1 ? ROUND_1_INCIDENTS : ROUND_2_INCIDENTS;
	}, []);

	const createNextIncident = useCallback(
		(roundIncidents: typeof ROUND_1_INCIDENTS) => {
			return async () => {
				const idx = createIndexRef.current;
				if (idx >= TOTAL_INCIDENTS) {
					if (intervalRef.current) {
						clearInterval(intervalRef.current);
						intervalRef.current = null;
					}
					return;
				}

				const inc = roundIncidents[idx];
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
			};
		},
		[apiUrl]
	);

	const startRound = useCallback(
		async (round: number, order: RoundMode[]) => {
			setPhase("resetting");
			setIncidents([]);
			createIndexRef.current = 0;

			// Set manual mode for this round
			const mode = order[round - 1];
			setManualMode(mode === "manual");

			// Reset system
			try {
				const res = await fetch(`${apiUrl}/admin/reset`, { method: "POST" });
				if (!res.ok) throw new Error(`HTTP ${res.status}`);
			} catch (err) {
				console.error("Reset failed:", err);
				alert("Failed to reset system.");
				setPhase("idle");
				setTestLocked(false);
				return;
			}

			// Wait a moment for reset to propagate
			await new Promise((r) => setTimeout(r, 1500));

			setPhase("round_running");

			const roundIncidents = getIncidentsForRound(round);
			const creator = createNextIncident(roundIncidents);
			creator();
			intervalRef.current = setInterval(creator, CREATE_INTERVAL_MS);

			timeoutRef.current = setTimeout(() => {
				setPhase((p) => {
					if (p === "round_running" || p === "round_waiting") return "tlx";
					return p;
				});
			}, TIMEOUT_MS);
		},
		[apiUrl, createNextIncident, getIncidentsForRound]
	);

	const startTest = useCallback(() => {
		if (phase !== "idle") return;
		setConsentModalOpen(true);
	}, [phase]);

	const confirmConsent = useCallback(async () => {
		setConsentModalOpen(false);

		// Randomize order
		const order: RoundMode[] =
			Math.random() < 0.5
				? ["manual", "optimizer"]
				: ["optimizer", "manual"];
		setRoundOrder(order);
		setCurrentRound(1);
		setTestLocked(true);
		setRound1Incidents([]);
		setRound2Incidents([]);
		setRound1TlxScores(null);
		setRound2TlxScores(null);

		// Create study record
		const roundOrderLabel =
			order[0] === "manual" ? "manual_first" : "optimizer_first";
		try {
			const res = await fetch(`${apiUrl}/user-studies`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ round_order: roundOrderLabel }),
			});
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			setStudyId(data.id);
		} catch (err) {
			console.error("Failed to create user study:", err);
			alert("Failed to start study. Check console for details.");
			setTestLocked(false);
			return;
		}

		startRound(1, order);
	}, [apiUrl, startRound]);

	const cancelConsent = useCallback(() => {
		setConsentModalOpen(false);
	}, []);

	const submitTlx = useCallback(
		async (scores: TlxScores) => {
			// Calculate avg dispatch time for this round
			const dispatched = incidents.filter((t) => t.dispatchedAt !== null);
			const avgMs =
				dispatched.length > 0
					? dispatched.reduce(
							(sum, t) => sum + (t.dispatchedAt! - t.createdAt),
							0
						) / dispatched.length
					: 0;

			const dispatchTimes = incidents.map((t) => ({
				incidentId: t.incidentId,
				priority: t.priority,
				type: t.type,
				location: t.location,
				timeMs: t.dispatchedAt ? t.dispatchedAt - t.createdAt : null,
			}));

			const mode = roundOrder[currentRound - 1];

			// Save round to backend
			if (studyId) {
				try {
					await fetch(`${apiUrl}/user-studies/rounds`, {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({
							study_id: studyId,
							round_number: currentRound,
							mode,
							dispatch_times: dispatchTimes,
							avg_dispatch_time_ms: avgMs,
							tlx_mental_demand: scores.mentalDemand,
							tlx_physical_demand: scores.physicalDemand,
							tlx_temporal_demand: scores.temporalDemand,
							tlx_effort: scores.effort,
							tlx_performance: scores.performance,
							tlx_frustration: scores.frustration,
						}),
					});
				} catch (err) {
					console.error("Failed to save study round:", err);
				}
			}

			if (currentRound === 1) {
				// Store round 1 results, start round 2
				setRound1Incidents([...incidents]);
				setRound1TlxScores(scores);
				setCurrentRound(2);
				startRound(2, roundOrder);
			} else {
				// Round 2 complete — show results (study completed on feedback submit)
				setRound2Incidents([...incidents]);
				setRound2TlxScores(scores);
				setTestLocked(false);
				setPhase("complete");
			}
		},
		[incidents, currentRound, roundOrder, studyId, apiUrl, startRound]
	);

	const submitFeedback = useCallback(
		async (feedback: string) => {
			if (studyId) {
				try {
					await fetch(`${apiUrl}/user-studies/${studyId}/complete`, {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ feedback: feedback || null }),
					});
				} catch (err) {
					console.error("Failed to complete study:", err);
				}
			}
		},
		[studyId, apiUrl]
	);

	const dismissResults = useCallback(() => {
		setPhase("idle");
		setIncidents([]);
		setStudyId(null);
		setCurrentRound(1);
		setTestLocked(false);
		setRound1Incidents([]);
		setRound2Incidents([]);
		setRound1TlxScores(null);
		setRound2TlxScores(null);
		createIndexRef.current = 0;
	}, []);

	const toggleManualMode = useCallback(() => {
		if (testLocked) return;
		setManualMode((prev) => !prev);
	}, [testLocked]);

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
				currentRound,
				roundOrder,
				testLocked,
				submitTlx,
				submitFeedback,
				round1Incidents,
				round2Incidents,
				round1TlxScores,
				round2TlxScores,
				studyId,
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
