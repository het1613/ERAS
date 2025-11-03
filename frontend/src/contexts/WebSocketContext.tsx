import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import io, { Socket } from 'socket.io-client'

interface WebSocketContextType {
  socket: Socket | null
  connected: boolean
}

const WebSocketContext = createContext<WebSocketContextType>({
  socket: null,
  connected: false,
})

export const useWebSocket = () => useContext(WebSocketContext)

interface WebSocketProviderProps {
  children: ReactNode
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const [socket, setSocket] = useState<Socket | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    // Note: Using native WebSocket since Socket.io might not be configured
    // In production, configure Socket.io properly or use native WebSocket
    const ws = new WebSocket('ws://localhost:8005/ws')

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onclose = () => {
      setConnected(false)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }

    // Store WebSocket reference
    setSocket(ws as any)

    return () => {
      ws.close()
    }
  }, [])

  return (
    <WebSocketContext.Provider value={{ socket, connected }}>
      {children}
    </WebSocketContext.Provider>
  )
}

