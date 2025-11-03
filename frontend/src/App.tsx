import React, { useState, useEffect } from 'react'
import Dashboard from './components/Dashboard'
import { WebSocketProvider } from './contexts/WebSocketContext'
import './App.css'

function App() {
  return (
    <WebSocketProvider>
      <Dashboard />
    </WebSocketProvider>
  )
}

export default App

