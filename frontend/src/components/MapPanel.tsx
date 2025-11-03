import React, { useEffect, useRef, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import { LatLngExpression } from 'leaflet'
import axios from 'axios'
import './MapPanel.css'

interface Vehicle {
  vehicle_id: string
  vehicle_type: string
  status: string
  location: { lat: number; lng: number }
}

interface MapPanelProps {
  sessionId: string | null
}

const MapPanel: React.FC<MapPanelProps> = ({ sessionId }) => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [incidentLocation, setIncidentLocation] = useState<LatLngExpression | null>(null)
  const [route, setRoute] = useState<LatLngExpression[] | null>(null)

  useEffect(() => {
    fetchVehicles()
    const interval = setInterval(fetchVehicles, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (sessionId) {
      fetchSessionIncidentLocation()
    }
  }, [sessionId])

  const fetchVehicles = async () => {
    try {
      const response = await axios.get('http://localhost:8005/api/v1/vehicles')
      setVehicles(response.data)
    } catch (error) {
      console.error('Error fetching vehicles:', error)
    }
  }

  const fetchSessionIncidentLocation = async () => {
    if (!sessionId) return
    
    try {
      const response = await axios.get(`http://localhost:8005/api/v1/sessions/${sessionId}`)
      const transcripts = response.data.transcripts || []
      
      // Get location from latest transcript
      const latestTranscript = transcripts[transcripts.length - 1]
      if (latestTranscript?.location) {
        setIncidentLocation([latestTranscript.location.lat, latestTranscript.location.lng])
      }
      
      // Get route from suggestions
      const suggestions = response.data.suggestions || []
      const routeSuggestion = suggestions.find((s: any) => s.type === 'route' && s.status === 'accepted')
      if (routeSuggestion?.content?.route) {
        const routeCoords = routeSuggestion.content.route.map((loc: any) => [loc.lat, loc.lng])
        setRoute(routeCoords)
      }
    } catch (error) {
      console.error('Error fetching session location:', error)
    }
  }

  const getVehicleIconColor = (status: string) => {
    switch (status) {
      case 'available':
        return 'green'
      case 'dispatched':
        return 'orange'
      case 'on_scene':
        return 'red'
      default:
        return 'gray'
    }
  }

  const center: LatLngExpression = [43.4723, -80.5449] // Default center (waterloo)

  return (
    <div className="map-panel">
      <div className="map-header">
        <h3>Vehicle Map</h3>
        <div className="vehicle-stats">
          <span>Available: {vehicles.filter(v => v.status === 'available').length}</span>
          <span>Dispatched: {vehicles.filter(v => v.status === 'dispatched').length}</span>
        </div>
      </div>
      
      <div className="map-container">
        <MapContainer
          center={incidentLocation || center}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          
          {/* Incident location marker */}
          {incidentLocation && (
            <Marker position={incidentLocation}>
              <Popup>
                <strong>Incident Location</strong>
                <br />
                {sessionId}
              </Popup>
            </Marker>
          )}
          
          {/* Vehicle markers */}
          {vehicles.map((vehicle) => (
            <Marker
              key={vehicle.vehicle_id}
              position={[vehicle.location.lat, vehicle.location.lng]}
            >
              <Popup>
                <strong>{vehicle.vehicle_id}</strong>
                <br />
                Type: {vehicle.vehicle_type}
                <br />
                Status: {vehicle.status}
              </Popup>
            </Marker>
          ))}
          
          {/* Route polyline */}
          {route && route.length > 1 && (
            <Polyline positions={route} color="#6366f1" weight={3} />
          )}
        </MapContainer>
      </div>
    </div>
  )
}

export default MapPanel

