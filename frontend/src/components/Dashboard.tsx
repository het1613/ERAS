import { useState } from 'react'
import TranscriptPanel from './TranscriptPanel'
import MapPanel from './MapPanel'
import './Dashboard.css'

const Dashboard = () => {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

  return (
    <div className="dashboard">
      <div className="dashboard-left">
        <TranscriptPanel 
          selectedSessionId={selectedSessionId}
          onSessionSelect={setSelectedSessionId}
        />
      </div>
      <div className="dashboard-right">
        <MapPanel sessionId={selectedSessionId} />
      </div>
    </div>
  )
}

export default Dashboard

