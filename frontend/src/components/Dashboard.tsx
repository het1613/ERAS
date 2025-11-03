import React, { useState, useEffect } from 'react'
import TranscriptPanel from './TranscriptPanel'
import MapPanel from './MapPanel'
import { useWebSocket } from '../contexts/WebSocketContext'
import axios from 'axios'
import './Dashboard.css'

interface Session {
  session_id: string
  status: string
  start_time: string
  incident_code?: string
}

const Dashboard: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const { socket, connected } = useWebSocket()

  useEffect(() => {
    fetchSessions()
    const interval = setInterval(fetchSessions, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (socket) {
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data)
        // Handle real-time updates
        if (data.type === 'transcript') {
          // Update transcript in real-time
        } else if (data.type === 'suggestion') {
          // Handle new suggestion
        }
      }
    }
  }, [socket])

  const fetchSessions = async () => {
    try {
      const response = await axios.get('http://localhost:8005/api/v1/sessions')
      setSessions(response.data)
      
      // Auto-select first active session if none selected
      if (!activeSessionId && response.data.length > 0) {
        const activeSession = response.data.find((s: Session) => s.status === 'active')
        if (activeSession) {
          setActiveSessionId(activeSession.session_id)
        }
      }
    } catch (error) {
      console.error('Error fetching sessions:', error)
    }
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>ERAS - Emergency Response Assistance System</h1>
        <div className="connection-status">
          <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`} />
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>
      
      <div className="dashboard-content">
        <div className="sessions-sidebar">
          <h2>Active Sessions</h2>
          <div className="sessions-list">
            {sessions.map((session) => (
              <div
                key={session.session_id}
                className={`session-item ${activeSessionId === session.session_id ? 'active' : ''}`}
                onClick={() => setActiveSessionId(session.session_id)}
              >
                <div className="session-id">{session.session_id.substring(0, 8)}...</div>
                <div className="session-status">{session.status}</div>
                {session.incident_code && (
                  <div className="incident-code">{session.incident_code}</div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="main-panel">
          <TranscriptPanel sessionId={activeSessionId} />
          <MapPanel sessionId={activeSessionId} />
        </div>
      </div>
    </div>
  )
}

export default Dashboard

