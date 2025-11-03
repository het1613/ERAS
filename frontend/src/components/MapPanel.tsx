import { useEffect, useState } from 'react'
import './MapPanel.css'

interface Vehicle {
  id: string
  lat: number
  lon: number
  status: string
  vehicle_type: string
}

interface AssignmentSuggestion {
  session_id: string
  suggested_vehicle_id: string
  route: string
  timestamp: string
}

interface MapPanelProps {
  sessionId: string | null
}

const MapPanel = ({ sessionId }: MapPanelProps) => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [assignment, setAssignment] = useState<AssignmentSuggestion | null>(null)

  useEffect(() => {
    // Fetch vehicles
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    fetch(`${apiUrl}/vehicles`)
      .then(res => res.json())
      .then(data => {
        setVehicles(data.vehicles || [])
      })
      .catch(err => console.error('Error fetching vehicles:', err))
  }, [])

  useEffect(() => {
    if (sessionId) {
      // Fetch assignment for selected session
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      fetch(`${apiUrl}/sessions/${sessionId}/assignment`)
        .then(res => {
          if (res.ok) {
            return res.json()
          }
          return null
        })
        .then(data => {
          setAssignment(data)
        })
        .catch(err => {
          console.error('Error fetching assignment:', err)
          setAssignment(null)
        })
    } else {
      setAssignment(null)
    }
  }, [sessionId])

  return (
    <div className="map-panel">
      <div className="map-panel-header">
        <h2>Map View</h2>
        {sessionId && (
          <span className="session-badge">Session: {sessionId.substring(0, 8)}...</span>
        )}
      </div>

      <div className="map-container">
        {/* Mocked map - placeholder */}
        <div className="map-placeholder">
          <div className="map-placeholder-content">
            <div className="map-icon">🗺️</div>
            <p>Map Visualization</p>
            <p className="map-subtitle">(Mocked for MVP)</p>
          </div>

          {/* Vehicle markers overlay */}
          <div className="vehicle-markers">
            {vehicles.map(vehicle => {
              // Mock positioning (in real implementation, would use actual lat/lon)
              const x = 50 + (vehicle.lat - 43.45) * 1000
              const y = 50 + (vehicle.lon + 80.52) * 1000
              
              return (
                <div
                  key={vehicle.id}
                  className={`vehicle-marker vehicle-${vehicle.status}`}
                  style={{
                    left: `${Math.max(10, Math.min(90, x))}%`,
                    top: `${Math.max(10, Math.min(90, y))}%`
                  }}
                  title={`${vehicle.id} (${vehicle.vehicle_type}) - ${vehicle.status}`}
                >
                  <div className="marker-dot"></div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="map-panel-sidebar">
        <div className="vehicles-section">
          <h3>Vehicles ({vehicles.length})</h3>
          <div className="vehicles-list">
            {vehicles.length === 0 ? (
              <div className="empty-state">No vehicles available</div>
            ) : (
              vehicles.map(vehicle => (
                <div key={vehicle.id} className={`vehicle-item vehicle-${vehicle.status}`}>
                  <div className="vehicle-header">
                    <span className="vehicle-id">{vehicle.id}</span>
                    <span className={`vehicle-status status-${vehicle.status}`}>
                      {vehicle.status}
                    </span>
                  </div>
                  <div className="vehicle-info">
                    <span className="vehicle-type">{vehicle.vehicle_type}</span>
                    <span className="vehicle-location">
                      {vehicle.lat.toFixed(4)}, {vehicle.lon.toFixed(4)}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {assignment && (
          <div className="assignment-section">
            <h3>Assignment</h3>
            <div className="assignment-details">
              <div className="assignment-item">
                <span className="assignment-label">Vehicle:</span>
                <span className="assignment-value">{assignment.suggested_vehicle_id}</span>
              </div>
              <div className="assignment-item">
                <span className="assignment-label">Route:</span>
                <span className="assignment-value">{assignment.route}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default MapPanel

