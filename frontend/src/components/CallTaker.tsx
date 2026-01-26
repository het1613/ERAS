import React, { useEffect, useState, useRef } from 'react';
import './CallTaker.css';

interface Transcript {
    session_id: string;
    text: string;
    timestamp: string;
    sender?: 'caller' | 'operator'; // Optional, defaults to caller if undefined
}

interface Suggestion {
    session_id: string;
    suggestion_type: string;
    value: string;
    status: string;
    timestamp: string;
}

const CallTaker: React.FC = () => {
    const [sessions, setSessions] = useState<string[]>([]);
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
    const [transcripts, setTranscripts] = useState<Transcript[]>([]);
    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [isConnected, setIsConnected] = useState(false);

    const transcriptsEndRef = useRef<HTMLDivElement>(null);

    // Initial Data Fetch
    useEffect(() => {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

        const fetchSessions = async () => {
            try {
                const response = await fetch(`${apiUrl}/sessions`);
                const data = await response.json();
                const sessionIds = data.sessions.map((s: any) => s.session_id);
                setSessions(sessionIds);
                if (sessionIds.length > 0 && !selectedSessionId) {
                    setSelectedSessionId(sessionIds[0]);
                }
            } catch (error) {
                console.error('Error fetching sessions:', error);
            }
        };

        fetchSessions();
    }, []);

    // WebSocket Connection
    useEffect(() => {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const wsUrl = apiUrl.replace(/^http/, 'ws') + '/ws';
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setIsConnected(true);
            console.log('CallTaker WebSocket connected');
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);

                if (message.type === 'transcript') {
                    const newTranscript = message.data as Transcript;

                    // Update sessions if new
                    setSessions(prev => {
                        if (!prev.includes(newTranscript.session_id)) {
                            return [newTranscript.session_id, ...prev];
                        }
                        return prev;
                    });

                    // Add transcript
                    setTranscripts(prev => {
                        // Avoid duplicates
                        const exists = prev.some(t =>
                            t.session_id === newTranscript.session_id &&
                            t.text === newTranscript.text &&
                            t.timestamp === newTranscript.timestamp
                        );
                        if (exists) return prev;
                        return [...prev, newTranscript];
                    });
                } else if (message.type === 'suggestion') {
                    const newSuggestion = message.data as Suggestion;
                    setSuggestions(prev => {
                        const exists = prev.some(s =>
                            s.session_id === newSuggestion.session_id &&
                            s.value === newSuggestion.value &&
                            s.timestamp === newSuggestion.timestamp
                        );
                        if (exists) return prev;
                        return [...prev, newSuggestion];
                    });
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
            console.log('CallTaker WebSocket disconnected');
        };

        return () => {
            ws.close();
        };
    }, []);

    // Fetch history when session changes
    useEffect(() => {
        if (!selectedSessionId) return;

        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

        // We only fetch if we don't have data, or to refresh
        // For simplicity, we'll fetch and merge/set
        // In a real app, you might want better caching

        const fetchData = async () => {
            try {
                const [transRes, suggRes] = await Promise.all([
                    fetch(`${apiUrl}/sessions/${selectedSessionId}/transcript`),
                    fetch(`${apiUrl}/sessions/${selectedSessionId}/suggestions`)
                ]);

                const transData = await transRes.json();
                const suggData = await suggRes.json();

                if (transData.transcripts) {
                    setTranscripts(prev => {
                        const currentSessionIds = prev.filter(t => t.session_id !== selectedSessionId);
                        return [...currentSessionIds, ...transData.transcripts];
                    });
                }

                if (suggData.suggestions) {
                    setSuggestions(prev => {
                        const currentSessionIds = prev.filter(s => s.session_id !== selectedSessionId);
                        return [...currentSessionIds, ...suggData.suggestions];
                    });
                }

            } catch (error) {
                console.error('Error fetching session data:', error);
            }
        };

        fetchData();
    }, [selectedSessionId]);

    // Auto-scroll to bottom of transcripts
    useEffect(() => {
        transcriptsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [transcripts, selectedSessionId]);

    const activeTranscripts = selectedSessionId
        ? transcripts
            .filter(t => t.session_id === selectedSessionId)
            .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        : [];

    const activeSuggestions = selectedSessionId
        ? suggestions
            .filter(s => s.session_id === selectedSessionId)
            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        : [];

    return (
        <div className="call-taker-container">
            {/* Sidebar: Sessions */}
            <div className="sidebar">
                <div className="sidebar-header">
                    <h2>Active Calls</h2>
                </div>
                <div className="sidebar-content">
                    {sessions.length === 0 ? (
                        <div className="empty-state">No Active Sessions</div>
                    ) : (
                        sessions.map(sessionId => (
                            <div
                                key={sessionId}
                                className={`session-item ${selectedSessionId === sessionId ? 'active' : ''}`}
                                onClick={() => setSelectedSessionId(sessionId)}
                            >
                                <span className="session-id">ID: {sessionId.substring(0, 8)}...</span>
                                <span className="session-time">Live</span>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Main: Transcript */}
            <div className="main-content">
                <div className="main-header">
                    <h2>
                        {selectedSessionId
                            ? `Live Transcript - ${selectedSessionId.substring(0, 8)}`
                            : 'Select a Call'}
                    </h2>
                    <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
                        {isConnected ? '● System Online' : '○ System Offline'}
                    </div>
                </div>

                <div className="transcript-area">
                    {activeTranscripts.length === 0 ? (
                        <div className="empty-state">
                            Waiting for audio...
                        </div>
                    ) : (
                        activeTranscripts.map((t, idx) => (
                            <div key={idx} className={`transcript-bubble ${t.sender || 'caller'}`}>
                                <span className="bubble-meta">
                                    {t.sender === 'operator' ? 'Operator' : 'Caller'} • {new Date(t.timestamp).toLocaleTimeString()}
                                </span>
                                <div className="bubble-text">{t.text}</div>
                            </div>
                        ))
                    )}
                    <div ref={transcriptsEndRef} />
                </div>
            </div>

            {/* Right: AI Suggestions */}
            <div className="suggestions-panel">
                <div className="suggestions-header">
                    <h3>
                        <span>✨</span> AI Analysis
                    </h3>
                </div>
                <div className="suggestions-list">
                    {activeSuggestions.length === 0 ? (
                        <div className="empty-state">
                            Analyzing conversation...
                        </div>
                    ) : (
                        activeSuggestions.map((s, idx) => (
                            <div key={idx} className="suggestion-card high-priority">
                                <span className="suggestion-type">{s.suggestion_type}</span>
                                <div className="suggestion-content">{s.value}</div>
                                <div className="suggestion-actions">
                                    <button className="action-btn">Accept</button>
                                    <button className="action-btn">Dismiss</button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};

export default CallTaker;
