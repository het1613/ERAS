import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import SuggestionBubble from './SuggestionBubble'
import './TranscriptPanel.css'

interface Transcript {
  transcript_id: number
  transcript: string
  confidence: number
  timestamp: string
  incident_type?: string
  severity?: string
}

interface Suggestion {
  suggestion_id: string
  type: string
  content: any
  confidence: number
  status: string
}

interface TranscriptPanelProps {
  sessionId: string | null
}

const TranscriptPanel: React.FC<TranscriptPanelProps> = ({ sessionId }) => {
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [session, setSession] = useState<any>(null)
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (sessionId) {
      fetchSessionData()
      const interval = setInterval(fetchSessionData, 2000)
      return () => clearInterval(interval)
    }
  }, [sessionId])

  useEffect(() => {
    // Auto-scroll to bottom
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcripts])

  const fetchSessionData = async () => {
    if (!sessionId) return
    
    try {
      const response = await axios.get(`http://localhost:8005/api/v1/sessions/${sessionId}`)
      setSession(response.data.session)
      setTranscripts(response.data.transcripts || [])
      setSuggestions(response.data.suggestions || [])
    } catch (error) {
      console.error('Error fetching session data:', error)
    }
  }

  const handleSuggestionAction = async (suggestionId: string, action: string) => {
    try {
      await axios.post(`http://localhost:8005/api/v1/suggestions/${suggestionId}/action`, {
        action
      })
      fetchSessionData()
    } catch (error) {
      console.error('Error handling suggestion action:', error)
    }
  }

  if (!sessionId) {
    return (
      <div className="transcript-panel">
        <div className="empty-state">Select a session to view transcripts</div>
      </div>
    )
  }

  return (
    <div className="transcript-panel">
      <div className="transcript-header">
        <h3>Call Transcript</h3>
        <div className="session-info">
          {session?.incident_code && (
            <span className="incident-badge">{session.incident_code}</span>
          )}
          <span className={`status-badge ${session?.status}`}>{session?.status}</span>
        </div>
      </div>
      
      <div className="transcript-content">
        {transcripts.map((transcript) => (
          <div key={transcript.transcript_id} className="transcript-item">
            <div className="transcript-meta">
              <span className="timestamp">
                {new Date(transcript.timestamp).toLocaleTimeString()}
              </span>
              <span className="confidence">{(transcript.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="transcript-text">{transcript.transcript}</div>
            {transcript.incident_type && (
              <div className="transcript-tags">
                <span className="tag incident">{transcript.incident_type}</span>
                {transcript.severity && (
                  <span className={`tag severity ${transcript.severity}`}>
                    {transcript.severity}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
        
        {/* Render suggestions inline */}
        {suggestions
          .filter(s => s.status === 'pending')
          .map((suggestion) => (
            <SuggestionBubble
              key={suggestion.suggestion_id}
              suggestion={suggestion}
              onAction={(action) => handleSuggestionAction(suggestion.suggestion_id, action)}
            />
          ))}
        
        <div ref={transcriptEndRef} />
      </div>
    </div>
  )
}

export default TranscriptPanel

