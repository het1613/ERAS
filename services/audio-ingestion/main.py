"""
Audio Ingestion Service - Receives audio input and publishes to Kafka.
"""

import os
import uuid
import logging
import sys
import asyncio
import base64
import json
from datetime import datetime
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from shared.kafka_client import create_producer
from shared.types import AudioChunk

# Add parent directory to path to access shared module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Audio Ingestion Service", version="0.1.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Kafka producer
producer = None


@app.on_event("startup")
async def startup_event():
    """Initialize Kafka producer on startup."""
    global producer
    try:
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        producer = create_producer(bootstrap_servers=bootstrap_servers)
        logger.info(f"Kafka producer initialized with bootstrap_servers: {bootstrap_servers}")
    except Exception as e:
        logger.error(f"Failed to initialize Kafka producer: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Close Kafka producer on shutdown."""
    global producer
    if producer:
        producer.close()
        logger.info("Kafka producer closed")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "audio-ingestion"}


@app.post("/ingest")
async def ingest_audio(file: UploadFile = File(...)):
    """
    Accept audio file upload and publish chunks to Kafka.
    """
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer not initialized")
    
    try:
        # Generate session ID for this audio ingestion
        session_id = str(uuid.uuid4())
        logger.info(f"Processing audio file for session: {session_id}")
        
        # Read file content
        file_content = await file.read()
        
        # Base64 encode the file content
        # In a real scenario, we might want to chunk this if the file is large
        chunk_data = base64.b64encode(file_content).decode('utf-8')
        
        chunk = AudioChunk(
            session_id=session_id,
            chunk_data=chunk_data,
            timestamp=datetime.now(),
            sequence_number=0
        )
        
        # Serialize and publish to Kafka
        chunk_dict = chunk.model_dump()
        chunk_dict['timestamp'] = chunk_dict['timestamp'].isoformat()
        
        producer.send("audio-chunks", chunk_dict)
        producer.flush()
        
        logger.info(f"Published audio chunk to Kafka for session: {session_id}")
        
        return {
            "session_id": session_id,
            "status": "ingested",
            "filename": file.filename,
            "size": len(file_content)
        }
        
    except Exception as e:
        logger.error(f"Error ingesting audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error ingesting audio: {str(e)}")


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio streaming.
    Receives audio blobs, buffers them, and publishes chunks to Kafka.
    """
    if producer is None:
        await websocket.close(code=1011, reason="Kafka producer not initialized")
        return

    await websocket.accept()
    
    session_id = str(uuid.uuid4())
    logger.info(f"WebSocket audio stream connected. Session ID: {session_id}")
    
    # Send session ID to client
    await websocket.send_json({"session_id": session_id, "status": "connected"})
    
    sequence_number = 0
    buffer = bytearray()
    # ~5 seconds of audio at 16kHz, 16-bit mono (16000 samples/sec * 2 bytes * 5 sec)
    # Whisper models need at least 3-5 seconds of audio for reliable transcription
    CHUNK_SIZE = 16000 * 2 * 5
    
    try:
        while True:
            # Receive audio data (can be bytes or text)
            # Frontend should send Blob/ArrayBuffer which comes as bytes
            data = await websocket.receive_bytes()
            
            if not data:
                break
                
            buffer.extend(data)
            
            # If buffer is large enough, create a chunk
            if len(buffer) >= CHUNK_SIZE:
                # Take a chunk
                chunk_bytes = buffer[:CHUNK_SIZE]
                buffer = buffer[CHUNK_SIZE:]
                
                # Base64 encode
                chunk_b64 = base64.b64encode(chunk_bytes).decode('utf-8')
                
                chunk = AudioChunk(
                    session_id=session_id,
                    chunk_data=chunk_b64,
                    timestamp=datetime.now(),
                    sequence_number=sequence_number
                )
                
                # Send to Kafka
                chunk_dict = chunk.model_dump()
                chunk_dict['timestamp'] = chunk_dict['timestamp'].isoformat()
                
                producer.send("audio-chunks", chunk_dict)
                # We typically don't flush every message for high throughput, 
                # but for low latency interactive app it might be better, or rely on internal batching with low latency config.
                # producer.flush() 
                
                sequence_number += 1
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
        
        # Only send remaining buffer if it contains enough audio for meaningful transcription.
        # At 16kHz 16-bit mono, 1 second = 32000 bytes. Fragments shorter than ~1.5s
        # are almost always silence/noise and cause Whisper to hallucinate.
        MIN_REMAINING_BYTES = 16000 * 2 * 1.5  # 1.5 seconds
        if len(buffer) >= MIN_REMAINING_BYTES:
            chunk_b64 = base64.b64encode(buffer).decode('utf-8')
            chunk = AudioChunk(
                session_id=session_id,
                chunk_data=chunk_b64,
                timestamp=datetime.now(),
                sequence_number=sequence_number
            )
            chunk_dict = chunk.model_dump()
            chunk_dict['timestamp'] = chunk_dict['timestamp'].isoformat()
            producer.send("audio-chunks", chunk_dict)
            producer.flush()
        elif len(buffer) > 0:
            logger.info(f"Discarding {len(buffer)} bytes of remaining audio (too short for reliable transcription)")
            
    except Exception as e:
        logger.error(f"Error in WebSocket stream: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except:
            pass
            
    finally:
        logger.info(f"Stream ended for session: {session_id}")


@app.websocket("/ws/twilio-stream")
async def twilio_stream_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    Twilio sends JSON messages with base64-encoded mu-law 8kHz audio.
    We convert to 16kHz PCM (matching the browser mic format) and publish to Kafka.
    """
    import audioop

    if producer is None:
        await websocket.close(code=1011, reason="Kafka producer not initialized")
        return

    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket connected")

    session_id = str(uuid.uuid4())
    call_sid = None
    caller_number = None
    sequence_number = 0
    buffer = bytearray()
    # Same 5-second chunk size as browser endpoint: 16kHz * 2 bytes * 5 sec
    CHUNK_SIZE = 16000 * 2 * 5
    # State for audioop.ratecv (maintains resampling continuity across calls)
    ratecv_state = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event_type = data.get("event")

            if event_type == "connected":
                logger.info(f"Twilio stream connected: {data}")

            elif event_type == "start":
                start_data = data.get("start", {})
                call_sid = start_data.get("callSid")
                caller_number = start_data.get("customParameters", {}).get("from") or start_data.get("from")
                logger.info(f"Twilio stream started. CallSid: {call_sid}, Caller: {caller_number}, Session: {session_id}")

            elif event_type == "media":
                payload = data.get("media", {}).get("payload", "")
                if not payload:
                    continue

                # Decode base64 mu-law audio from Twilio
                mulaw_bytes = base64.b64decode(payload)
                # Convert mu-law to 16-bit linear PCM
                pcm_8khz = audioop.ulaw2lin(mulaw_bytes, 2)
                # Resample 8kHz -> 16kHz
                pcm_16khz, ratecv_state = audioop.ratecv(pcm_8khz, 2, 1, 8000, 16000, ratecv_state)

                buffer.extend(pcm_16khz)

                # Publish chunks at the same size as browser endpoint
                while len(buffer) >= CHUNK_SIZE:
                    chunk_bytes = bytes(buffer[:CHUNK_SIZE])
                    buffer = buffer[CHUNK_SIZE:]

                    chunk_b64 = base64.b64encode(chunk_bytes).decode('utf-8')
                    chunk = AudioChunk(
                        session_id=session_id,
                        chunk_data=chunk_b64,
                        timestamp=datetime.now(),
                        sequence_number=sequence_number,
                        call_source="phone",
                        caller_number=caller_number,
                    )

                    chunk_dict = chunk.model_dump()
                    chunk_dict['timestamp'] = chunk_dict['timestamp'].isoformat()
                    producer.send("audio-chunks", chunk_dict)

                    sequence_number += 1

            elif event_type == "stop":
                logger.info(f"Twilio stream stopped. CallSid: {call_sid}, Session: {session_id}")
                break

    except WebSocketDisconnect:
        logger.info(f"Twilio WebSocket disconnected. CallSid: {call_sid}, Session: {session_id}")

    except Exception as e:
        logger.error(f"Error in Twilio stream: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

    finally:
        # Flush remaining buffer if it has enough audio (~1.5 seconds)
        MIN_REMAINING_BYTES = int(16000 * 2 * 1.5)
        if len(buffer) >= MIN_REMAINING_BYTES:
            chunk_b64 = base64.b64encode(bytes(buffer)).decode('utf-8')
            chunk = AudioChunk(
                session_id=session_id,
                chunk_data=chunk_b64,
                timestamp=datetime.now(),
                sequence_number=sequence_number,
                call_source="phone",
                caller_number=caller_number,
            )
            chunk_dict = chunk.model_dump()
            chunk_dict['timestamp'] = chunk_dict['timestamp'].isoformat()
            producer.send("audio-chunks", chunk_dict)
            producer.flush()
        elif len(buffer) > 0:
            logger.info(f"Discarding {len(buffer)} bytes of remaining Twilio audio (too short for reliable transcription)")

        logger.info(f"Twilio stream ended. CallSid: {call_sid}, Session: {session_id}")


@app.post("/twilio/voice")
async def twilio_voice_webhook():
    """
    TwiML webhook for incoming Twilio calls.
    Returns TwiML that plays a greeting and connects to the Media Stream.
    Configure your Twilio phone number's Voice webhook to point here.
    """
    # Build the WebSocket URL for the Media Stream.
    # In production, set TWILIO_STREAM_URL env var to your public WSS URL.
    # With ngrok: wss://<ngrok-subdomain>.ngrok-free.app/ws/twilio-stream
    stream_url = os.getenv("TWILIO_STREAM_URL", "wss://localhost:8001/ws/twilio-stream")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello, nine one one, what is your emergency?</Say>
    <Connect>
        <Stream url="{stream_url}" track="inbound_track" />
    </Connect>
</Response>"""

    from fastapi.responses import Response
    return Response(content=twiml, media_type="application/xml")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

