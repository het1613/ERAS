import React, { useState, useRef, useEffect } from 'react';
import './Caller.css'; // We'll create this CSS file too

const Caller: React.FC = () => {
    const [isCallActive, setIsCallActive] = useState(false);
    const [status, setStatus] = useState<string>('Ready to call');
    const [sessionId, setSessionId] = useState<string | null>(null);

    // Refs for WebSocket and Audio
    const wsRef = useRef<WebSocket | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

    // Audio configuration
    const TARGET_SAMPLE_RATE = 16000;
    const BUFFER_SIZE = 4096;

    const convertFloat32ToInt16 = (buffer: Float32Array): Int16Array => {
        let l = buffer.length;
        const buf = new Int16Array(l);
        while (l--) {
            buf[l] = Math.min(1, Math.max(-1, buffer[l])) * 0x7FFF;
        }
        return buf;
    };

    // Simple downsampler as fallback, but we prefer native browser resampling
    const downsampleBuffer = (buffer: Float32Array, sampleRate: number, outSampleRate: number): Float32Array => {
        if (outSampleRate === sampleRate) {
            return buffer;
        }
        if (outSampleRate > sampleRate) {
            // Upsampling (shouldn't happen with 16k target) - just return as is or error
            return buffer;
        }
        const sampleRateRatio = sampleRate / outSampleRate;
        const newLength = Math.round(buffer.length / sampleRateRatio);
        const result = new Float32Array(newLength);
        let offsetResult = 0;
        let offsetBuffer = 0;
        while (offsetResult < result.length) {
            const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
            // Use average value of skipped samples
            let accum = 0, count = 0;
            for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
                accum += buffer[i];
                count++;
            }
            result[offsetResult] = accum / count;
            offsetResult++;
            offsetBuffer = nextOffsetBuffer;
        }
        return result;
    };

    const startCall = async () => {
        try {
            setStatus('Connecting...');

            // Connect to WebSocket
            const ws = new WebSocket('ws://localhost:8001/ws/stream');

            ws.onopen = async () => {
                console.log('Connected to Audio Ingestion Service');
                setStatus('Connected. Starting audio...');

                try {
                    // Get microphone access - request standard settings
                    const stream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            channelCount: 1,
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true
                        }
                    });
                    streamRef.current = stream;

                    // Initialize AudioContext with preferred sample rate
                    // Browsers that support this will handle high-quality resampling automatically
                    const AudioContextClass = (window.AudioContext || (window as any).webkitAudioContext);
                    const audioContext = new AudioContextClass({ sampleRate: TARGET_SAMPLE_RATE });
                    audioContextRef.current = audioContext;

                    console.log(`AudioContext created with sample rate: ${audioContext.sampleRate}Hz`);

                    const source = audioContext.createMediaStreamSource(stream);
                    sourceRef.current = source;

                    // Create ScriptProcessor
                    // bufferSize, inputChannels, outputChannels
                    const processor = audioContext.createScriptProcessor(BUFFER_SIZE, 1, 1);
                    processorRef.current = processor;

                    processor.onaudioprocess = (e) => {
                        if (ws.readyState !== WebSocket.OPEN) return;

                        const inputData = e.inputBuffer.getChannelData(0); // Mono

                        // If browser respected our sampleRate request, this is a no-op 1:1 copy
                        // If not, we fall back to our simple downsampler
                        const downsampled = downsampleBuffer(inputData, audioContext.sampleRate, TARGET_SAMPLE_RATE);

                        // Convert to Int16
                        const pcm16 = convertFloat32ToInt16(downsampled);

                        // Send as raw bytes
                        ws.send(pcm16.buffer);
                    };

                    // Connect graph
                    source.connect(processor);
                    processor.connect(audioContext.destination); // Needed for processing to happen

                    setStatus('Call in progress...');
                    setIsCallActive(true);

                } catch (err) {
                    console.error('Error accessing microphone:', err);
                    setStatus('Error: Could not access microphone');
                    ws.close();
                }
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.session_id) {
                    setSessionId(data.session_id);
                }
            };

            ws.onclose = () => {
                console.log('Disconnected from Audio Ingestion Service');
                if (isCallActive) {
                    endCall();
                }
                setStatus('Call ended');
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                setStatus('Connection error');
            };

            wsRef.current = ws;

        } catch (err) {
            console.error('Error starting call:', err);
            setStatus('Error starting call');
        }
    };

    const endCall = () => {
        // Stop Audio Processing
        if (processorRef.current && sourceRef.current) {
            sourceRef.current.disconnect();
            processorRef.current.disconnect();
        }

        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        // Stop microphone stream
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }

        // Close WebSocket
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }

        setIsCallActive(false);
        setStatus('Call ended');
        setSessionId(null);
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (isCallActive) {
                endCall();
            }
        };
    }, [isCallActive]);

    return (
        <div className="caller-container">
            <div className="caller-card">
                <h1>911 Simulator</h1>

                <div className={`status-indicator ${isCallActive ? 'active' : ''}`}>
                    {status}
                </div>

                {sessionId && (
                    <div className="session-info">
                        Session ID: {sessionId}
                    </div>
                )}

                <div className="controls">
                    {!isCallActive ? (
                        <button className="call-btn start-call" onClick={startCall}>
                            Call 911
                        </button>
                    ) : (
                        <button className="call-btn end-call" onClick={endCall}>
                            End Call
                        </button>
                    )}
                </div>

                <div className="info-text">
                    <p>Click "Call 911" to start streaming audio to the ERAS system.</p>
                    <p>Your microphone will be used to simulate a caller.</p>
                </div>
            </div>
        </div>
    );
};

export default Caller;
