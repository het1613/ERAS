import { createContext, useContext, useEffect, useRef, useState, useCallback, ReactNode } from "react";

interface WebSocketMessage {
	type: string;
	data: any;
}

type MessageHandler = (msg: WebSocketMessage) => void;

interface WebSocketContextValue {
	connected: boolean;
	subscribe: (handler: MessageHandler) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

const RECONNECT_DELAY_MS = 2000;

export function WebSocketProvider({ children }: { children: ReactNode }) {
	const [connected, setConnected] = useState(false);
	const handlersRef = useRef<Set<MessageHandler>>(new Set());
	const wsRef = useRef<WebSocket | null>(null);
	const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

	const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

	const connect = useCallback(() => {
		if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
			return;
		}

		const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws";
		const ws = new WebSocket(wsUrl);

		ws.onopen = () => setConnected(true);

		ws.onmessage = (event) => {
			try {
				const msg: WebSocketMessage = JSON.parse(event.data);
				for (const handler of handlersRef.current) {
					handler(msg);
				}
			} catch (err) {
				console.error("Error parsing WS message:", err);
			}
		};

		ws.onerror = (err) => console.error("WebSocket error:", err);

		ws.onclose = () => {
			setConnected(false);
			wsRef.current = null;
			reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
		};

		wsRef.current = ws;
	}, [apiUrl]);

	useEffect(() => {
		connect();
		return () => {
			if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
			wsRef.current?.close();
		};
	}, [connect]);

	const subscribe = useCallback((handler: MessageHandler) => {
		handlersRef.current.add(handler);
		return () => {
			handlersRef.current.delete(handler);
		};
	}, []);

	return (
		<WebSocketContext.Provider value={{ connected, subscribe }}>
			{children}
		</WebSocketContext.Provider>
	);
}

export function useWebSocket() {
	const ctx = useContext(WebSocketContext);
	if (!ctx) throw new Error("useWebSocket must be used within WebSocketProvider");
	return ctx;
}

export function useWebSocketMessage(type: string | string[], handler: MessageHandler) {
	const { subscribe } = useWebSocket();
	const handlerRef = useRef(handler);
	handlerRef.current = handler;

	const types = Array.isArray(type) ? type : [type];
	const typesKey = types.join(",");

	useEffect(() => {
		return subscribe((msg) => {
			if (types.includes(msg.type)) {
				handlerRef.current(msg);
			}
		});
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [subscribe, typesKey]);
}
