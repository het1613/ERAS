import { useEffect, useState } from 'react'
import './TranscriptPanel.css'

interface Transcript {
  session_id: string
  text: string
  timestamp: string
}

interface Suggestion {
  session_id: string
  suggestion_type: string
  value: string
  status: string
  timestamp: string
}

interface TranscriptPanelProps {
  selectedSessionId: string | null
  onSessionSelect: (sessionId: string | null) => void
}

const TranscriptPanel = ({ selectedSessionId, onSessionSelect }: TranscriptPanelProps) => {
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [sessions, setSessions] = useState<string[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    // Connect to WebSocket
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const wsUrl = apiUrl.replace(/^http/, 'ws') + '/ws'
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setConnected(true)
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        
        if (message.type === 'transcript') {
          const transcript = message.data as Transcript
          setTranscripts(prev => {
            const updated = [...prev, transcript]
            // Update sessions list
            if (!sessions.includes(transcript.session_id)) {
              setSessions(prev => [...prev, transcript.session_id])
            }
            return updated
          })
        } else if (message.type === 'suggestion') {
          const suggestion = message.data as Suggestion
          setSuggestions(prev => {
            const updated = [...prev, suggestion]
            return updated
          })
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }

    ws.onclose = () => {
      setConnected(false)
      console.log('WebSocket disconnected')
    }

    // Fetch existing sessions on mount
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    fetch(`${apiUrl}/sessions`)
      .then(res => res.json())
      .then(data => {
        const sessionIds = data.sessions.map((s: any) => s.session_id)
        setSessions(sessionIds)
      })
      .catch(err => console.error('Error fetching sessions:', err))

    return () => {
      ws.close()
    }
  }, [])

  const filteredTranscripts = selectedSessionId
    ? transcripts.filter(t => t.session_id === selectedSessionId)
    : transcripts

  const filteredSuggestions = selectedSessionId
    ? suggestions.filter(s => s.session_id === selectedSessionId)
    : suggestions

  return (
    <div className="transcript-panel">
      <div className="transcript-panel-header">
        <h2>Transcripts & Suggestions</h2>
        <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? '● Connected' : '○ Disconnected'}
        </div>
      </div>
      
      <div className="transcript-panel-sessions">
        <div className="session-list">
          <button
            className={`session-button ${!selectedSessionId ? 'active' : ''}`}
            onClick={() => onSessionSelect(null)}
          >
            All Sessions
          </button>
          {sessions.map(sessionId => (
            <button
              key={sessionId}
              className={`session-button ${selectedSessionId === sessionId ? 'active' : ''}`}
              onClick={() => onSessionSelect(sessionId)}
            >
              {sessionId.substring(0, 8)}...
            </button>
          ))}
        </div>
      </div>

      <div className="transcript-panel-content">
        <div className="transcripts-section">
          <h3>Transcripts</h3>
          <div className="transcripts-list">
            {filteredTranscripts.length === 0 ? (
              <div className="empty-state">No transcripts yet</div>
            ) : (
              filteredTranscripts.map((transcript, idx) => (
                <div key={idx} className="transcript-item">
                  <div className="transcript-meta">
                    <span className="session-id">{transcript.session_id.substring(0, 8)}...</span>
                    <span className="timestamp">{new Date(transcript.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="transcript-text">{transcript.text}</div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="suggestions-section">
          <h3>AI Suggestions</h3>
          <div className="suggestions-list">
            {filteredSuggestions.length === 0 ? (
              <div className="empty-state">No suggestions yet</div>
            ) : (
              filteredSuggestions.map((suggestion, idx) => (
                <div key={idx} className={`suggestion-item suggestion-${suggestion.status}`}>
                  <div className="suggestion-header">
                    <span className="suggestion-type">{suggestion.suggestion_type}</span>
                    <span className="suggestion-status">{suggestion.status}</span>
                  </div>
                  <div className="suggestion-value">{suggestion.value}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default TranscriptPanel

