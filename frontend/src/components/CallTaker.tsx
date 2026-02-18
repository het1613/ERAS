import React, { useEffect, useState, useRef, useCallback } from 'react';
import './CallTaker.css';

interface Transcript {
    session_id: string;
    text: string;
    timestamp: string;
    sender?: 'caller' | 'operator';
}

interface Suggestion {
    id: string;
    session_id: string;
    suggestion_type: string;
    value: string;
    status: string;
    timestamp: string;
    incident_code: string | null;
    incident_code_description: string | null;
    incident_code_category: string | null;
    priority: string | null;
    confidence: number | null;
    extracted_location: string | null;
    extracted_lat: number | null;
    extracted_lon: number | null;
}

interface AcrCode {
    code: string;
    description: string;
    category: string;
    default_priority: string;
}

type CasePriority = 'Purple' | 'Red' | 'Orange' | 'Yellow' | 'Green';

const PRIORITY_COLORS: Record<CasePriority, string> = {
    Purple: '#884dff',
    Red: '#d6455d',
    Orange: '#e29a00',
    Yellow: '#d4a700',
    Green: '#2e994e',
};

const PRIORITIES: CasePriority[] = ['Purple', 'Red', 'Orange', 'Yellow', 'Green'];

const CallTaker: React.FC = () => {
    const [sessions, setSessions] = useState<string[]>([]);
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
    const [transcripts, setTranscripts] = useState<Transcript[]>([]);
    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [acrCodes, setAcrCodes] = useState<AcrCode[]>([]);

    // Per-suggestion editable overrides: suggestion.id -> { code, priority, lat, lon, location }
    const [overrides, setOverrides] = useState<Record<string, {
        incident_code: string;
        priority: string;
        lat: string;
        lon: string;
        location: string;
    }>>({});

    const [acceptingId, setAcceptingId] = useState<string | null>(null);

    const transcriptsEndRef = useRef<HTMLDivElement>(null);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    // Fetch ACR codes on mount
    useEffect(() => {
        const fetchAcrCodes = async () => {
            try {
                const res = await fetch(`${apiUrl}/acr-codes`);
                const data = await res.json();
                setAcrCodes(data.codes || []);
            } catch (error) {
                console.error('Error fetching ACR codes:', error);
            }
        };
        fetchAcrCodes();
    }, [apiUrl]);

    // Initialize overrides when a new suggestion arrives, using LLM-extracted location if available
    const ensureOverride = useCallback((s: Suggestion) => {
        setOverrides(prev => {
            if (prev[s.id]) return prev;
            return {
                ...prev,
                [s.id]: {
                    incident_code: s.incident_code || '',
                    priority: s.priority || 'Yellow',
                    lat: s.extracted_lat != null ? String(s.extracted_lat) : '43.4643',
                    lon: s.extracted_lon != null ? String(s.extracted_lon) : '-80.5205',
                    location: s.extracted_location || '',
                },
            };
        });
    }, []);

    // Initial Data Fetch
    useEffect(() => {
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
    }, [apiUrl]);

    // WebSocket Connection
    useEffect(() => {
        const wsUrl = apiUrl.replace(/^http/, 'ws') + '/ws';
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);

                if (message.type === 'transcript') {
                    const newTranscript = message.data as Transcript;
                    setSessions(prev => {
                        if (!prev.includes(newTranscript.session_id)) {
                            return [newTranscript.session_id, ...prev];
                        }
                        return prev;
                    });
                    setTranscripts(prev => {
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
                        const exists = prev.some(s => s.id === newSuggestion.id);
                        if (exists) return prev;
                        return [...prev, newSuggestion];
                    });
                    ensureOverride(newSuggestion);
                } else if (message.type === 'suggestion_updated') {
                    const updated = message.data as Suggestion;
                    setSuggestions(prev =>
                        prev.map(s => s.id === updated.id ? updated : s)
                    );
                    // Update location fields from AI extraction
                    if (updated.extracted_location) {
                        setOverrides(prev => {
                            const existing = prev[updated.id];
                            if (!existing) return prev;
                            return {
                                ...prev,
                                [updated.id]: {
                                    ...existing,
                                    location: updated.extracted_location ?? existing.location,
                                    lat: updated.extracted_lat != null ? String(updated.extracted_lat) : existing.lat,
                                    lon: updated.extracted_lon != null ? String(updated.extracted_lon) : existing.lon,
                                },
                            };
                        });
                    }
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
        };

        return () => {
            ws.close();
        };
    }, [apiUrl, ensureOverride]);

    // Fetch history when session changes
    useEffect(() => {
        if (!selectedSessionId) return;

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
                        const other = prev.filter(t => t.session_id !== selectedSessionId);
                        return [...other, ...transData.transcripts];
                    });
                }

                if (suggData.suggestions) {
                    const newSuggs = suggData.suggestions as Suggestion[];
                    setSuggestions(prev => {
                        const other = prev.filter(s => s.session_id !== selectedSessionId);
                        return [...other, ...newSuggs];
                    });
                    newSuggs.forEach(ensureOverride);
                }
            } catch (error) {
                console.error('Error fetching session data:', error);
            }
        };

        fetchData();
    }, [selectedSessionId, apiUrl, ensureOverride]);

    // Auto-scroll to bottom of transcripts
    useEffect(() => {
        transcriptsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [transcripts, selectedSessionId]);

    const updateOverride = (suggestionId: string, field: string, value: string) => {
        setOverrides(prev => ({
            ...prev,
            [suggestionId]: {
                ...prev[suggestionId],
                [field]: value,
            }
        }));

        // When code changes, auto-update priority to the code's default
        if (field === 'incident_code') {
            const selectedCode = acrCodes.find(c => c.code === value);
            if (selectedCode) {
                setOverrides(prev => ({
                    ...prev,
                    [suggestionId]: {
                        ...prev[suggestionId],
                        incident_code: value,
                        priority: selectedCode.default_priority,
                    }
                }));
            }
        }
    };

    const handleAccept = async (suggestion: Suggestion) => {
        const override = overrides[suggestion.id];
        if (!override) return;

        const lat = parseFloat(override.lat);
        const lon = parseFloat(override.lon);
        if (isNaN(lat) || isNaN(lon)) {
            alert('Please enter valid latitude and longitude values.');
            return;
        }

        setAcceptingId(suggestion.id);

        // Look up full code details for the override
        const selectedCode = acrCodes.find(c => c.code === override.incident_code);

        try {
            const res = await fetch(`${apiUrl}/suggestions/${suggestion.id}/accept`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    incident_code: override.incident_code || suggestion.incident_code,
                    incident_code_description: selectedCode?.description || suggestion.incident_code_description,
                    incident_code_category: selectedCode?.category || suggestion.incident_code_category,
                    priority: override.priority || suggestion.priority,
                    lat,
                    lon,
                    location: override.location || null,
                }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
        } catch (error) {
            console.error('Error accepting suggestion:', error);
            alert(error instanceof Error ? error.message : 'Failed to accept suggestion');
        } finally {
            setAcceptingId(null);
        }
    };

    const handleDismiss = async (suggestion: Suggestion) => {
        try {
            const res = await fetch(`${apiUrl}/suggestions/${suggestion.id}/dismiss`, {
                method: 'POST',
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
        } catch (error) {
            console.error('Error dismissing suggestion:', error);
        }
    };

    const activeTranscripts = selectedSessionId
        ? transcripts
            .filter(t => t.session_id === selectedSessionId)
            .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        : [];

    const activeSuggestions = selectedSessionId
        ? suggestions
            .filter(s => s.session_id === selectedSessionId && s.status === 'pending')
            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        : [];

    // Group ACR codes by category for the dropdown
    const codesByCategory: Record<string, AcrCode[]> = {};
    acrCodes.forEach(c => {
        if (!codesByCategory[c.category]) codesByCategory[c.category] = [];
        codesByCategory[c.category].push(c);
    });

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
                        activeSuggestions.map((s) => {
                            const override = overrides[s.id];
                            const displayPriority = (override?.priority || s.priority || 'Yellow') as CasePriority;
                            const priorityColor = PRIORITY_COLORS[displayPriority] || '#888';
                            const confidence = s.confidence != null ? Math.round(s.confidence * 100) : null;

                            return (
                                <div key={s.id} className="suggestion-card" style={{ borderLeftColor: priorityColor }}>
                                    {/* Header: Category + Code */}
                                    <div className="suggestion-card-header">
                                        {s.incident_code_category && (
                                            <span className="category-badge">{s.incident_code_category}</span>
                                        )}
                                        {s.incident_code && (
                                            <span className="code-badge">Code {s.incident_code}</span>
                                        )}
                                        {confidence !== null && (
                                            <span className="confidence-badge" title="Match confidence">
                                                {confidence}%
                                            </span>
                                        )}
                                    </div>

                                    {/* Description */}
                                    <div className="suggestion-description">
                                        {s.incident_code_description || s.value}
                                    </div>

                                    {/* Priority badge */}
                                    <div className="priority-display">
                                        <span
                                            className="priority-dot"
                                            style={{ backgroundColor: priorityColor }}
                                        />
                                        <span className="priority-label" style={{ color: priorityColor }}>
                                            {displayPriority} Priority
                                        </span>
                                    </div>

                                    {/* Editable Fields */}
                                    {override && (
                                        <div className="suggestion-edit-fields">
                                            <div className="edit-row">
                                                <label>Incident Code</label>
                                                <select
                                                    value={override.incident_code}
                                                    onChange={(e) => updateOverride(s.id, 'incident_code', e.target.value)}
                                                >
                                                    <option value="">-- Select --</option>
                                                    {Object.entries(codesByCategory).map(([category, codes]) => (
                                                        <optgroup key={category} label={category}>
                                                            {codes.map(c => (
                                                                <option key={c.code} value={c.code}>
                                                                    {c.code} - {c.description}
                                                                </option>
                                                            ))}
                                                        </optgroup>
                                                    ))}
                                                </select>
                                            </div>

                                            <div className="edit-row">
                                                <label>Priority</label>
                                                <select
                                                    value={override.priority}
                                                    onChange={(e) => updateOverride(s.id, 'priority', e.target.value)}
                                                    style={{ borderColor: PRIORITY_COLORS[override.priority as CasePriority] || '#ccc' }}
                                                >
                                                    {PRIORITIES.map(p => (
                                                        <option key={p} value={p}>{p}</option>
                                                    ))}
                                                </select>
                                            </div>

                                            <div className="edit-row">
                                                <label>
                                                    Location
                                                    {s.extracted_location && (
                                                        <span className="ai-extracted-badge" title="Auto-extracted from transcript by AI">AI</span>
                                                    )}
                                                </label>
                                                <input
                                                    type="text"
                                                    placeholder="e.g. 234 Columbia St"
                                                    value={override.location}
                                                    onChange={(e) => updateOverride(s.id, 'location', e.target.value)}
                                                />
                                            </div>

                                            <div className="edit-row-pair">
                                                <div className="edit-row half">
                                                    <label>
                                                        Lat
                                                        {s.extracted_lat != null && (
                                                            <span className="ai-extracted-badge" title="Geocoded from AI-extracted location">AI</span>
                                                        )}
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={override.lat}
                                                        onChange={(e) => updateOverride(s.id, 'lat', e.target.value)}
                                                    />
                                                </div>
                                                <div className="edit-row half">
                                                    <label>
                                                        Lon
                                                        {s.extracted_lon != null && (
                                                            <span className="ai-extracted-badge" title="Geocoded from AI-extracted location">AI</span>
                                                        )}
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={override.lon}
                                                        onChange={(e) => updateOverride(s.id, 'lon', e.target.value)}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Actions */}
                                    <div className="suggestion-actions">
                                        <button
                                            className="action-btn accept-btn"
                                            disabled={acceptingId === s.id}
                                            onClick={() => handleAccept(s)}
                                        >
                                            {acceptingId === s.id ? 'Creating...' : 'Accept & Create Incident'}
                                        </button>
                                        <button
                                            className="action-btn dismiss-btn"
                                            onClick={() => handleDismiss(s)}
                                        >
                                            Dismiss
                                        </button>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>
        </div>
    );
};

export default CallTaker;
