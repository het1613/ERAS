import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import {
  Phone, Search, MapPin, ChevronDown, ChevronRight,
  Pencil, Check, X, AlertTriangle, BrainCircuit, Plus, PhoneOff
} from 'lucide-react';
import Badge from './ui/Badge';
import Button from './ui/Button';
import ConfidenceBar from './ui/ConfidenceBar';
import ConfirmDialog from './ui/ConfirmDialog';
import EmptyState from './ui/EmptyState';
import RevisionHistory, { Revision } from './ui/RevisionHistory';
import './CallTaker.css';

interface Transcript {
  session_id: string;
  text: string;
  timestamp: string;
  sender?: 'caller' | 'operator';
}

interface MatchedEvidence {
  keyword: string;
  score: number;
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
  matched_evidence: MatchedEvidence[] | null;
  extracted_location: string | null;
  extracted_lat: number | null;
  extracted_lon: number | null;
  location_confidence: number | null;
}

interface AcrCode {
  code: string;
  description: string;
  category: string;
  default_priority: string;
}

type CasePriority = 'Purple' | 'Red' | 'Orange' | 'Yellow' | 'Green';

const PRIORITY_COLORS: Record<CasePriority, string> = {
  Purple: 'var(--priority-purple)',
  Red: 'var(--priority-red)',
  Orange: 'var(--priority-orange)',
  Yellow: 'var(--priority-yellow)',
  Green: 'var(--priority-green)',
};

const PRIORITY_BGS: Record<CasePriority, string> = {
  Purple: 'var(--priority-purple-bg)',
  Red: 'var(--priority-red-bg)',
  Orange: 'var(--priority-orange-bg)',
  Yellow: 'var(--priority-yellow-bg)',
  Green: 'var(--priority-green-bg)',
};

const PRIORITIES: CasePriority[] = ['Purple', 'Red', 'Orange', 'Yellow', 'Green'];

/** Parse ISO timestamp as UTC when backend sends naive datetime (no Z). */
function parseUtc(iso: string): Date {
  if (!iso) return new Date();
  const s = iso.trim();
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s) && !s.endsWith('Z') && !/[-+]\d{2}:?\d{2}$/.test(s)) {
    return new Date(s + 'Z');
  }
  return new Date(s);
}

const EST_OPTS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'America/New_York',
};
const EST_OPTS_SEC: Intl.DateTimeFormatOptions = { ...EST_OPTS, second: '2-digit' };

interface SessionMeta {
  id: string;
  startTime: string;
  index: number;
  lastActivityTime: number;
}

const CallTaker: React.FC = () => {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [acrCodes, setAcrCodes] = useState<AcrCode[]>([]);
  const [codeSearchQuery, setCodeSearchQuery] = useState('');
  const [hoveredSuggestionId, setHoveredSuggestionId] = useState<string | null>(null);

  const [overrides, setOverrides] = useState<Record<string, {
    incident_code: string;
    priority: string;
    lat: string;
    lon: string;
    location: string;
  }>>({});

  const [revisions, setRevisions] = useState<Record<string, Revision[]>>({});
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [geocodingId, setGeocodingId] = useState<string | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<{ suggestion: Suggestion; override: typeof overrides[string] } | null>(null);
  const [editingLocationId, setEditingLocationId] = useState<string | null>(null);
  const [showCoordsId, setShowCoordsId] = useState<string | null>(null);
  const [openCodeDropdownId, setOpenCodeDropdownId] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<Record<string, { field: string; aiValue: string; currentValue: string }>>({});
  const [lastSuggestionTime, setLastSuggestionTime] = useState<number>(Date.now());

  const [now, setNow] = useState(Date.now());
  const transcriptsEndRef = useRef<HTMLDivElement>(null);
  const sessionCounterRef = useRef(0);
  const codeDropdownRef = useRef<HTMLDivElement>(null);
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(interval);
  }, []);

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

  useEffect(() => {
    if (!openCodeDropdownId) return;
    const onMouseDown = (e: MouseEvent) => {
      if (codeDropdownRef.current && !codeDropdownRef.current.contains(e.target as Node)) {
        setOpenCodeDropdownId(null);
        setCodeSearchQuery('');
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpenCodeDropdownId(null);
        setCodeSearchQuery('');
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [openCodeDropdownId]);

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

  const addSession = useCallback((sessionId: string, isLiveEvent = false, startTime?: string) => {
    setSessions(prev => {
      if (prev.some(s => s.id === sessionId)) return prev;
      sessionCounterRef.current += 1;
      return [{
        id: sessionId,
        startTime: startTime || new Date().toISOString(),
        index: sessionCounterRef.current,
        lastActivityTime: isLiveEvent ? Date.now() : 0,
      }, ...prev];
    });
  }, []);

  const touchSession = useCallback((sessionId: string) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId ? { ...s, lastActivityTime: Date.now() } : s
    ));
  }, []);

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const response = await fetch(`${apiUrl}/sessions`);
        const data = await response.json();
        const list = data.sessions || [];
        list.forEach((s: { session_id: string; created_at?: string }) =>
          addSession(s.session_id, false, s.created_at)
        );
        if (list.length > 0 && !selectedSessionId) {
          setSelectedSessionId(list[0].session_id);
        }
      } catch (error) {
        console.error('Error fetching sessions:', error);
      }
    };
    fetchSessions();
  }, [apiUrl, addSession]);

  useEffect(() => {
    const wsUrl = apiUrl.replace(/^http/, 'ws') + '/ws';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setIsConnected(true);

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'transcript') {
          const t = message.data as Transcript;
          addSession(t.session_id, true, t.timestamp);
          touchSession(t.session_id);
          setTranscripts(prev => {
            const exists = prev.some(x => x.session_id === t.session_id && x.text === t.text && x.timestamp === t.timestamp);
            if (exists) return prev;
            return [...prev, t];
          });
        } else if (message.type === 'suggestion') {
          const s = message.data as Suggestion;
          setSuggestions(prev => {
            const exists = prev.some(x => x.id === s.id);
            if (exists) return prev;
            return [...prev, s];
          });
          ensureOverride(s);
          setLastSuggestionTime(Date.now());
        } else if (message.type === 'suggestion_updated') {
          const updated = message.data as Suggestion;
          setSuggestions(prev => prev.map(s => s.id === updated.id ? updated : s));
          if (updated.extracted_location) {
            setOverrides(prev => {
              const existing = prev[updated.id];
              if (!existing) return prev;
              const oldLocation = existing.location;
              const newLocation = updated.extracted_location ?? existing.location;
              if (oldLocation && oldLocation !== newLocation && oldLocation !== '') {
                setConflicts(c => ({
                  ...c,
                  [updated.id]: { field: 'location', aiValue: newLocation, currentValue: oldLocation }
                }));
              }
              return {
                ...prev,
                [updated.id]: {
                  ...existing,
                  location: oldLocation || newLocation,
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

    ws.onclose = () => setIsConnected(false);
    return () => ws.close();
  }, [apiUrl, ensureOverride, addSession, touchSession]);

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

  useEffect(() => {
    transcriptsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts, selectedSessionId]);

  const addRevision = (suggestionId: string, field: string, oldValue: string, newValue: string) => {
    if (oldValue === newValue) return;
    setRevisions(prev => ({
      ...prev,
      [suggestionId]: [...(prev[suggestionId] || []), {
        timestamp: new Date().toISOString(),
        field,
        oldValue,
        newValue,
        actor: 'operator' as const,
      }],
    }));
  };

  const updateOverride = (suggestionId: string, field: string, value: string) => {
    setOverrides(prev => {
      const old = prev[suggestionId];
      if (old) addRevision(suggestionId, field, (old as any)[field], value);
      return { ...prev, [suggestionId]: { ...old, [field]: value } };
    });

    if (field === 'incident_code') {
      const selectedCode = acrCodes.find(c => c.code === value);
      if (selectedCode) {
        setOverrides(prev => ({
          ...prev,
          [suggestionId]: { ...prev[suggestionId], incident_code: value, priority: selectedCode.default_priority },
        }));
      }
    }
  };

  const geocodeLocation = useCallback(async (suggestionId: string, address: string) => {
    if (!address.trim()) return;
    setGeocodingId(suggestionId);
    try {
      const res = await fetch(`${apiUrl}/geocode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.found) {
        setOverrides(prev => ({
          ...prev,
          [suggestionId]: { ...prev[suggestionId], lat: String(data.lat), lon: String(data.lon) },
        }));
      }
    } catch (error) {
      console.error('Geocoding error:', error);
    } finally {
      setGeocodingId(null);
      setEditingLocationId(null);
    }
  }, [apiUrl]);

  const handleAcceptConfirm = async () => {
    if (!confirmDialog) return;
    const { suggestion, override } = confirmDialog;
    const lat = parseFloat(override.lat);
    const lon = parseFloat(override.lon);
    if (isNaN(lat) || isNaN(lon)) {
      alert('Please enter valid latitude and longitude values.');
      return;
    }
    setAcceptingId(suggestion.id);
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
          lat, lon,
          location: override.location || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setConfirmDialog(null);
    } catch (error) {
      console.error('Error accepting suggestion:', error);
      alert(error instanceof Error ? error.message : 'Failed to accept suggestion');
    } finally {
      setAcceptingId(null);
    }
  };

  const handleDismiss = async (suggestion: Suggestion) => {
    try {
      await fetch(`${apiUrl}/suggestions/${suggestion.id}/dismiss`, { method: 'POST' });
    } catch (error) {
      console.error('Error dismissing suggestion:', error);
    }
  };

  const resolveConflict = (suggestionId: string, useAi: boolean) => {
    const conflict = conflicts[suggestionId];
    if (!conflict) return;
    if (useAi) {
      updateOverride(suggestionId, conflict.field, conflict.aiValue);
    }
    setConflicts(prev => {
      const next = { ...prev };
      delete next[suggestionId];
      return next;
    });
  };

  const activeTranscripts = selectedSessionId
    ? transcripts.filter(t => t.session_id === selectedSessionId).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    : [];

  const activeSuggestions = selectedSessionId
    ? suggestions.filter(s => s.session_id === selectedSessionId && s.status === 'pending').sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    : [];

  const hoveredEvidence = useMemo(() => {
    if (!hoveredSuggestionId) return new Set<string>();
    const s = suggestions.find(x => x.id === hoveredSuggestionId);
    if (!s?.matched_evidence) return new Set<string>();
    return new Set(s.matched_evidence.map(e => e.keyword.toLowerCase()));
  }, [hoveredSuggestionId, suggestions]);

  const codesByCategory = useMemo(() => {
    const map: Record<string, AcrCode[]> = {};
    const query = codeSearchQuery.toLowerCase().trim();
    acrCodes.forEach(c => {
      if (query && !c.description.toLowerCase().includes(query) && !c.code.toLowerCase().includes(query) && !c.category.toLowerCase().includes(query)) return;
      if (!map[c.category]) map[c.category] = [];
      map[c.category].push(c);
    });
    return map;
  }, [acrCodes, codeSearchQuery]);

  const filteredCodeCount = useMemo(() => {
    return Object.values(codesByCategory).reduce((sum, codes) => sum + codes.length, 0);
  }, [codesByCategory]);

  const SESSION_IDLE_TIMEOUT = 15000;
  const isSessionLive = (session: SessionMeta) => now - session.lastActivityTime < SESSION_IDLE_TIMEOUT;

  const showFailSoft = isConnected && selectedSessionId && activeSuggestions.length === 0 && Date.now() - lastSuggestionTime > 30000;
  const selectedSession = sessions.find(s => s.id === selectedSessionId);

  const highlightTranscript = (text: string): React.ReactNode => {
    if (hoveredEvidence.size === 0) return text;
    const lower = text.toLowerCase();
    const segments: { start: number; end: number; keyword: string }[] = [];
    for (const kw of hoveredEvidence) {
      let idx = 0;
      while ((idx = lower.indexOf(kw, idx)) !== -1) {
        segments.push({ start: idx, end: idx + kw.length, keyword: kw });
        idx += kw.length;
      }
    }
    if (segments.length === 0) return text;
    segments.sort((a, b) => a.start - b.start);

    const merged: typeof segments = [];
    for (const seg of segments) {
      if (merged.length > 0 && seg.start <= merged[merged.length - 1].end) {
        merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, seg.end);
      } else {
        merged.push({ ...seg });
      }
    }

    const parts: React.ReactNode[] = [];
    let cursor = 0;
    for (const seg of merged) {
      if (cursor < seg.start) parts.push(text.slice(cursor, seg.start));
      parts.push(
        <mark key={seg.start} className="ct-highlight">{text.slice(seg.start, seg.end)}</mark>
      );
      cursor = seg.end;
    }
    if (cursor < text.length) parts.push(text.slice(cursor));
    return parts;
  };

  return (
    <div className="ct-container">
      {/* Sidebar */}
      <div className="ct-sidebar">
        <div className="ct-sidebar-header">
          <Phone size={14} />
          <span>Active Calls</span>
          <span className="ct-call-count">{sessions.length}</span>
        </div>
        <div className="ct-sidebar-list">
          {sessions.length === 0 ? (
            <EmptyState title="No active calls" description="Waiting for incoming calls..." />
          ) : (
            sessions.map(session => {
              const live = isSessionLive(session);
              return (
                <button
                  key={session.id}
                  className={`ct-session-item ${selectedSessionId === session.id ? 'active' : ''}`}
                  onClick={() => setSelectedSessionId(session.id)}
                >
                  <div className="ct-session-info">
                    <span className="ct-session-label">Call #{session.index}</span>
                    <span className="ct-session-time">
                      {parseUtc(session.startTime).toLocaleTimeString('en-US', EST_OPTS)}
                    </span>
                  </div>
                  {live ? (
                    <span className="ct-session-live">LIVE</span>
                  ) : (
                    <span className="ct-session-ended"><PhoneOff size={10} /> Ended</span>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Center: Transcript */}
      <div className="ct-main">
        <div className="ct-main-header">
          <div className="ct-main-title">
            {selectedSession
              ? <>Live Transcript &mdash; Call #{selectedSession.index}</>
              : 'Select a Call'}
          </div>
        </div>
        <div className="ct-transcript-scroll">
          {activeTranscripts.length === 0 ? (
            <div className="ct-transcript-empty">
              <EmptyState title="Waiting for audio..." description="Transcript will appear here when the caller speaks." />
            </div>
          ) : (
            <div className="ct-transcript-inner">
              {activeTranscripts.map((t, idx) => (
                <div key={idx} className={`ct-message-row ${t.sender || 'caller'}`}>
                  <div className={`ct-bubble ${t.sender || 'caller'}`}>
                    <div className="ct-bubble-text">{highlightTranscript(t.text)}</div>
                  </div>
                  <span className="ct-bubble-time">
                    {parseUtc(t.timestamp).toLocaleTimeString('en-US', EST_OPTS_SEC)}
                  </span>
                </div>
              ))}
              <div ref={transcriptsEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Right: AI Suggestions */}
      <div className="ct-suggestions">
        <div className="ct-suggestions-header">
          <BrainCircuit size={14} />
          <span>AI Suggestions</span>
          {activeSuggestions.length > 0 && (
            <Badge variant="info" size="sm">{activeSuggestions.length}</Badge>
          )}
        </div>
        <div className="ct-suggestions-list">
          {activeSuggestions.length === 0 && !showFailSoft && (
            <EmptyState title="Analyzing conversation..." description="AI suggestions will appear as patterns are detected." />
          )}

          {showFailSoft && (
            <div className="ct-failsoft-card">
              <div className="ct-failsoft-header">
                <AlertTriangle size={14} />
                <span>No AI suggestions available</span>
              </div>
              <p className="ct-failsoft-desc">Create an incident manually if needed.</p>
              <Button variant="secondary" size="sm" icon={<Plus size={13} />} fullWidth>
                Manual Incident Entry
              </Button>
            </div>
          )}

          {activeSuggestions.map(s => {
            const override = overrides[s.id];
            const displayPriority = (override?.priority || s.priority || 'Yellow') as CasePriority;
            const conflict = conflicts[s.id];
            const suggestionRevisions = revisions[s.id] || [];

            return (
              <div
                key={s.id}
                className="ct-card"
                style={{ borderTopColor: PRIORITY_COLORS[displayPriority] }}
                onMouseEnter={() => setHoveredSuggestionId(s.id)}
                onMouseLeave={() => setHoveredSuggestionId(null)}
              >
                {/* Card Header */}
                <div className="ct-card-header">
                  <div className="ct-card-badges">
                    {s.incident_code_category && <Badge variant="neutral" size="sm">{s.incident_code_category}</Badge>}
                    {s.incident_code && <Badge variant="info" size="sm">Code {s.incident_code}</Badge>}
                  </div>
                  <Badge variant="priority" size="sm" dot color={PRIORITY_COLORS[displayPriority]} bg={PRIORITY_BGS[displayPriority]}>
                    {displayPriority}
                  </Badge>
                </div>

                {/* Description */}
                <div className="ct-card-title">
                  {s.incident_code_description || s.value}
                </div>

                {/* Confidence */}
                {s.confidence != null && (
                  <div className="ct-card-section">
                    <ConfidenceBar value={s.confidence} />
                  </div>
                )}

                {/* Evidence */}
                {s.matched_evidence && s.matched_evidence.length > 0 && (
                  <div className="ct-card-evidence">
                    <div className="ct-evidence-label">Matched keywords</div>
                    <div className="ct-evidence-chips">
                      {s.matched_evidence.map((e, i) => (
                        <span key={i} className="ct-evidence-chip">{e.keyword}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Conflict Banner */}
                {conflict && (
                  <div className="ct-conflict">
                    <AlertTriangle size={13} />
                    <span>AI updated {conflict.field}: &ldquo;{conflict.aiValue}&rdquo;</span>
                    <div className="ct-conflict-actions">
                      <button className="ct-conflict-btn" onClick={() => resolveConflict(s.id, true)}>Use AI</button>
                      <button className="ct-conflict-btn" onClick={() => resolveConflict(s.id, false)}>Keep Current</button>
                    </div>
                  </div>
                )}

                {/* Editable Fields */}
                {override && (
                  <div className="ct-card-fields">
                    {/* Location */}
                    <div className="ct-field">
                      <div className="ct-field-label">
                        <MapPin size={11} />
                        <span>Location</span>
                        {s.extracted_location && <Badge variant="info" size="sm">AI</Badge>}
                        {s.location_confidence != null && s.location_confidence < 0.5 && (
                          <Badge variant="warning" size="sm">Unverified</Badge>
                        )}
                      </div>
                      {editingLocationId === s.id ? (
                        <div className="ct-field-edit-row">
                          <input
                            type="text"
                            className="ct-input"
                            value={override.location}
                            onChange={e => updateOverride(s.id, 'location', e.target.value)}
                            onBlur={e => geocodeLocation(s.id, e.target.value)}
                            autoFocus
                            placeholder="e.g. 234 Columbia St"
                          />
                          <button className="ct-icon-btn" onClick={() => setEditingLocationId(null)}><Check size={13} /></button>
                        </div>
                      ) : (
                        <div className="ct-location-display">
                          <span className="ct-location-address">
                            {override.location || <span className="ct-placeholder">No location set</span>}
                          </span>
                          <button className="ct-icon-btn" onClick={() => setEditingLocationId(s.id)}>
                            <Pencil size={12} />
                          </button>
                          {geocodingId === s.id && <span className="ct-spinner" />}
                        </div>
                      )}
                      {/* Collapsible coords */}
                      <button className="ct-coords-toggle" onClick={() => setShowCoordsId(showCoordsId === s.id ? null : s.id)}>
                        {showCoordsId === s.id ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                        <span>{override.lat}, {override.lon}</span>
                      </button>
                      {showCoordsId === s.id && (
                        <div className="ct-coords-edit">
                          <div className="ct-field-half">
                            <label className="ct-mini-label">Lat</label>
                            <input type="text" className="ct-input ct-input-sm" value={override.lat} onChange={e => updateOverride(s.id, 'lat', e.target.value)} />
                          </div>
                          <div className="ct-field-half">
                            <label className="ct-mini-label">Lon</label>
                            <input type="text" className="ct-input ct-input-sm" value={override.lon} onChange={e => updateOverride(s.id, 'lon', e.target.value)} />
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Incident Code */}
                    <div className="ct-field">
                      <div className="ct-field-label">
                        <span>Incident Code</span>
                      </div>
                      <div
                        className={`ct-code-combobox ${openCodeDropdownId === s.id ? 'ct-code-combobox-open' : ''}`}
                        ref={openCodeDropdownId === s.id ? codeDropdownRef : undefined}
                      >
                        <button
                          type="button"
                          className={`ct-code-trigger ${!override.incident_code ? 'ct-code-trigger-placeholder' : ''}`}
                          onClick={() => setOpenCodeDropdownId(prev => prev === s.id ? null : s.id)}
                          aria-expanded={openCodeDropdownId === s.id}
                          aria-haspopup="listbox"
                        >
                          <span className="ct-code-trigger-text">
                            {override.incident_code
                              ? (() => {
                                  const sel = acrCodes.find(c => c.code === override.incident_code);
                                  return sel ? `${sel.code} — ${sel.description}` : override.incident_code;
                                })()
                              : 'Search incident code...'}
                          </span>
                          <ChevronDown size={14} className="ct-code-trigger-icon" aria-hidden />
                        </button>
                        {openCodeDropdownId === s.id && (
                          <div className="ct-code-dropdown" role="listbox">
                            <div className="ct-code-search">
                              <Search size={12} className="ct-code-search-icon" aria-hidden />
                              <input
                                type="text"
                                className="ct-input ct-code-search-input"
                                placeholder="Search by code or description..."
                                value={codeSearchQuery}
                                onChange={e => setCodeSearchQuery(e.target.value)}
                                autoFocus
                                aria-label="Filter incident codes"
                              />
                              {codeSearchQuery && (
                                <span className="ct-code-search-count">{filteredCodeCount} results</span>
                              )}
                            </div>
                            <div className="ct-code-list">
                              {override.incident_code && (
                                <button
                                  type="button"
                                  className="ct-code-option ct-code-option-clear"
                                  onClick={() => {
                                    updateOverride(s.id, 'incident_code', '');
                                    setOpenCodeDropdownId(null);
                                    setCodeSearchQuery('');
                                  }}
                                >
                                  Clear selection
                                </button>
                              )}
                              {Object.entries(codesByCategory).map(([category, codes]) => (
                                <div key={category} className="ct-code-group">
                                  <div className="ct-code-group-label">{category}</div>
                                  {codes.map(c => (
                                    <button
                                      key={c.code}
                                      type="button"
                                      role="option"
                                      className={`ct-code-option ${override.incident_code === c.code ? 'ct-code-option-selected' : ''}`}
                                      onClick={() => {
                                        updateOverride(s.id, 'incident_code', c.code);
                                        setOpenCodeDropdownId(null);
                                        setCodeSearchQuery('');
                                      }}
                                    >
                                      <span className="ct-code-option-code">{c.code}</span>
                                      <span className="ct-code-option-desc">{c.description}</span>
                                    </button>
                                  ))}
                                </div>
                              ))}
                              {filteredCodeCount === 0 && !override.incident_code && (
                                <div className="ct-code-empty">No codes match your search.</div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Priority */}
                    <div className="ct-field">
                      <div className="ct-field-label"><span>Priority</span></div>
                      <div className="ct-priority-select">
                        <span className="ct-priority-dot" style={{ backgroundColor: PRIORITY_COLORS[displayPriority] }} />
                        <select
                          className="ct-select"
                          value={override.priority}
                          onChange={e => updateOverride(s.id, 'priority', e.target.value)}
                        >
                          {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                        </select>
                      </div>
                    </div>
                  </div>
                )}

                {/* Revision History */}
                <RevisionHistory revisions={suggestionRevisions} />

                {/* Actions */}
                <div className="ct-card-actions">
                  <Button
                    variant="success"
                    size="sm"
                    icon={<Check size={13} />}
                    onClick={() => override && setConfirmDialog({ suggestion: s, override })}
                    disabled={acceptingId === s.id}
                    loading={acceptingId === s.id}
                  >
                    Accept & Create Incident
                  </Button>
                  <Button variant="ghost" size="sm" icon={<X size={13} />} onClick={() => handleDismiss(s)}>
                    Dismiss
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Confirm Dialog */}
      {confirmDialog && (
        <ConfirmDialog
          open={true}
          title="Create Incident"
          confirmLabel="Create Incident"
          variant="success"
          loading={acceptingId === confirmDialog.suggestion.id}
          onConfirm={handleAcceptConfirm}
          onCancel={() => setConfirmDialog(null)}
        >
          <div className="ct-confirm-summary">
            <div className="ct-confirm-row">
              <span className="ct-confirm-label">Type</span>
              <span>{confirmDialog.suggestion.incident_code_description || confirmDialog.suggestion.value}</span>
            </div>
            <div className="ct-confirm-row">
              <span className="ct-confirm-label">Code</span>
              <span>{confirmDialog.override.incident_code || 'None'}</span>
            </div>
            <div className="ct-confirm-row">
              <span className="ct-confirm-label">Priority</span>
              <Badge variant="priority" dot color={PRIORITY_COLORS[confirmDialog.override.priority as CasePriority]} bg={PRIORITY_BGS[confirmDialog.override.priority as CasePriority]}>
                {confirmDialog.override.priority}
              </Badge>
            </div>
            <div className="ct-confirm-row">
              <span className="ct-confirm-label">Location</span>
              <span>{confirmDialog.override.location || `${confirmDialog.override.lat}, ${confirmDialog.override.lon}`}</span>
            </div>
          </div>
        </ConfirmDialog>
      )}
    </div>
  );
};

export default CallTaker;
