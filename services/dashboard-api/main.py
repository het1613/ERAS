"""Dashboard API Service - Backend API for frontend dashboard."""
import os
import sys
from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import asyncio
import threading

# Add shared module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.redis_client import create_redis_client, get_session_data
from shared.kafka_client import create_consumer, create_producer, consume_messages
from shared.types import Session, ProcessedTranscript, AISuggestion

app = FastAPI(title="Dashboard API Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_client = create_redis_client()
producer = create_producer()

# Database connection
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_DB = os.getenv("POSTGRES_DB", "eras_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "eras_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "eras_password")


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.pubsub_running = False
        self.message_queue = []
        self.queue_lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Start Redis pubsub listener if not already running
        if not self.pubsub_running:
            self.start_redis_listener()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    def queue_message(self, message: dict):
        """Queue a message for broadcasting."""
        with self.queue_lock:
            self.message_queue.append(message)
    
    def get_queued_messages(self) -> List[dict]:
        """Get and clear queued messages."""
        with self.queue_lock:
            messages = self.message_queue[:]
            self.message_queue.clear()
            return messages
    
    def start_redis_listener(self):
        """Start background thread to listen to Redis pubsub."""
        def listen():
            self.pubsub_running = True
            pubsub = redis_client.pubsub()
            pubsub.psubscribe("transcript:*", "suggestion:*", "dispatch:*")
            
            for message in pubsub.listen():
                if message['type'] == 'pmessage':
                    try:
                        data = json.loads(message['data'])
                        # Queue for broadcast
                        self.queue_message(data)
                    except Exception as e:
                        print(f"Error processing Redis message: {e}")
        
        thread = threading.Thread(target=listen, daemon=True)
        thread.start()


# Background task to process message queue
async def process_message_queue():
    """Background task to process and broadcast queued messages."""
    while True:
        messages = manager.get_queued_messages()
        for msg in messages:
            await manager.broadcast(msg)
        await asyncio.sleep(0.1)


manager = ConnectionManager()


@app.get("/api/v1/sessions")
async def get_sessions(status: Optional[str] = None):
    """Get all sessions, optionally filtered by status."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if status:
                cur.execute("SELECT * FROM sessions WHERE status = %s ORDER BY start_time DESC", (status,))
            else:
                cur.execute("SELECT * FROM sessions ORDER BY start_time DESC")
            
            sessions = cur.fetchall()
            return [dict(s) for s in sessions]
    finally:
        conn.close()


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
            session = cur.fetchone()
            
            if not session:
                return JSONResponse({"error": "Session not found"}, status_code=404)
            
            # Get transcripts
            cur.execute(
                "SELECT * FROM transcripts WHERE session_id = %s ORDER BY timestamp",
                (session_id,)
            )
            transcripts = cur.fetchall()
            
            # Get suggestions
            cur.execute(
                "SELECT * FROM suggestions WHERE session_id = %s ORDER BY timestamp",
                (session_id,)
            )
            suggestions = cur.fetchall()
            
            return {
                "session": dict(session),
                "transcripts": [dict(t) for t in transcripts],
                "suggestions": [dict(s) for s in suggestions]
            }
    finally:
        conn.close()


@app.post("/api/v1/suggestions/{suggestion_id}/action")
async def handle_suggestion_action(suggestion_id: str, action: dict):
    """Handle suggestion action (accept/decline/modify)."""
    conn = get_db_connection()
    try:
        action_type = action.get("action")  # accept, decline, modify
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Update suggestion status
            cur.execute("""
                UPDATE suggestions 
                SET status = %s 
                WHERE suggestion_id = %s
            """, (action_type, suggestion_id))
            
            if action_type == "accept":
                # Get suggestion details
                cur.execute("SELECT * FROM suggestions WHERE suggestion_id = %s", (suggestion_id,))
                suggestion = cur.fetchone()
                
                if suggestion:
                    # Apply suggestion to session
                    if suggestion['type'] == 'incident_code':
                        cur.execute("""
                            UPDATE sessions 
                            SET incident_code = %s 
                            WHERE session_id = %s
                        """, (suggestion['content'].get('code'), suggestion['session_id']))
            
            conn.commit()
            
            # Broadcast update via WebSocket
            broadcast_msg = {
                "type": "suggestion_action",
                "suggestion_id": suggestion_id,
                "action": action_type,
                "session_id": suggestion['session_id'] if suggestion else None
            }
            await manager.broadcast(broadcast_msg)
            
            return {"status": "success", "action": action_type}
    finally:
        conn.close()


@app.get("/api/v1/vehicles")
async def get_vehicles(status: Optional[str] = None):
    """Get all vehicles."""
    # Proxy to geospatial-dispatch service
    import httpx
    async with httpx.AsyncClient() as client:
        url = f"http://geospatial-dispatch:8004/api/v1/vehicles"
        if status:
            url += f"?status={status}"
        response = await client.get(url)
        return response.json()


@app.post("/api/v1/dispatch")
async def dispatch(command: dict):
    """Create dispatch command."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://geospatial-dispatch:8004/api/v1/dispatch",
            json=command
        )
        return response.json()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    
    try:
        # Listen for messages from client
        while True:
            try:
                # Wait for message (or timeout)
                await websocket.receive_text()
            except:
                # Client disconnected or error
                break
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup():
    """Start background tasks on service startup."""
    # Start message queue processor
    asyncio.create_task(process_message_queue())


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dashboard-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

