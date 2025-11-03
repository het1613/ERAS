import React from 'react'
import './SuggestionBubble.css'

interface Suggestion {
  suggestion_id: string
  type: string
  content: any
  confidence: number
  status: string
}

interface SuggestionBubbleProps {
  suggestion: Suggestion
  onAction: (action: string) => void
}

const SuggestionBubble: React.FC<SuggestionBubbleProps> = ({ suggestion, onAction }) => {
  const getSuggestionColor = () => {
    switch (suggestion.type) {
      case 'incident_code':
        return '#4a5f7a'
      case 'severity':
        return '#f59e0b'
      case 'vehicle':
        return '#10b981'
      case 'route':
        return '#6366f1'
      case 'alert':
        return '#ef4444'
      default:
        return '#3a3f5a'
    }
  }

  const getSuggestionLabel = () => {
    switch (suggestion.type) {
      case 'incident_code':
        return 'Incident Code'
      case 'severity':
        return 'Severity'
      case 'vehicle':
        return 'Vehicle Suggestion'
      case 'route':
        return 'Route Suggestion'
      case 'alert':
        return 'Alert'
      default:
        return 'Suggestion'
    }
  }

  return (
    <div className="suggestion-bubble" style={{ borderLeftColor: getSuggestionColor() }}>
      <div className="suggestion-header">
        <span className="suggestion-label" style={{ background: getSuggestionColor() }}>
          {getSuggestionLabel()}
        </span>
        <span className="suggestion-confidence">
          {(suggestion.confidence * 100).toFixed(0)}%
        </span>
      </div>
      
      <div className="suggestion-content">
        {suggestion.type === 'incident_code' && (
          <div>
            <strong>Code:</strong> {suggestion.content.code}
            {suggestion.content.description && (
              <div className="suggestion-description">{suggestion.content.description}</div>
            )}
          </div>
        )}
        
        {suggestion.type === 'severity' && (
          <div>
            <strong>Severity:</strong> {suggestion.content.severity}
          </div>
        )}
        
        {suggestion.type === 'vehicle' && (
          <div>
            <strong>Vehicle:</strong> {suggestion.content.vehicle_id}
            <div className="suggestion-description">
              Type: {suggestion.content.vehicle_type} | 
              Distance: {suggestion.content.distance_km?.toFixed(1)} km
            </div>
          </div>
        )}
        
        {suggestion.type === 'route' && (
          <div>
            <strong>Route:</strong> {suggestion.content.distance_km?.toFixed(1)} km
          </div>
        )}
        
        {suggestion.type === 'alert' && (
          <div>
            <strong>Alert:</strong> {suggestion.content.message}
          </div>
        )}
      </div>
      
      <div className="suggestion-actions">
        <button 
          className="action-btn accept"
          onClick={() => onAction('accept')}
        >
          Accept
        </button>
        <button 
          className="action-btn decline"
          onClick={() => onAction('decline')}
        >
          Decline
        </button>
        <button 
          className="action-btn modify"
          onClick={() => onAction('modify')}
        >
          Modify
        </button>
      </div>
    </div>
  )
}

export default SuggestionBubble

