import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Phone, PhoneOff, Mic, Radio } from 'lucide-react';
import Button from './ui/Button';
import './Caller.css';

type CallState = 'ready' | 'connecting' | 'active' | 'ended';

const Caller: React.FC = () => {
  const [callState, setCallState] = useState<CallState>('ready');
  const [status, setStatus] = useState('Ready to call');
  const [transcripts, setTranscripts] = useState<{ text: string; time: string }[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const dashWsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const TARGET_SAMPLE_RATE = 16000;
  const BUFFER_SIZE = 4096;

  const convertFloat32ToInt16 = (buffer: Float32Array): Int16Array => {
    let l = buffer.length;
    const buf = new Int16Array(l);
    while (l--) buf[l] = Math.min(1, Math.max(-1, buffer[l])) * 0x7FFF;
    return buf;
  };

  const downsampleBuffer = (buffer: Float32Array, sampleRate: number, outSampleRate: number): Float32Array => {
    if (outSampleRate >= sampleRate) return buffer;
    const ratio = sampleRate / outSampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const nextOffset = Math.round((i + 1) * ratio);
      let accum = 0, count = 0;
      for (let j = Math.round(i * ratio); j < nextOffset && j < buffer.length; j++) {
        accum += buffer[j];
        count++;
      }
      result[i] = accum / count;
    }
    return result;
  };

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current) return;
    const data = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(data);
    const avg = data.reduce((a, b) => a + b, 0) / data.length;
    setAudioLevel(avg / 255);
    animFrameRef.current = requestAnimationFrame(updateAudioLevel);
  }, []);

  const startCall = async () => {
    try {
      setCallState('connecting');
      setStatus('Connecting...');
      setTranscripts([]);
      setElapsed(0);

      const ws = new WebSocket('ws://localhost:8001/ws/stream');

      ws.onopen = async () => {
        setStatus('Connected. Starting audio...');
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          });
          streamRef.current = stream;

          const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
          const audioContext = new AudioContextClass({ sampleRate: TARGET_SAMPLE_RATE });
          audioContextRef.current = audioContext;

          const source = audioContext.createMediaStreamSource(stream);
          sourceRef.current = source;

          const analyser = audioContext.createAnalyser();
          analyser.fftSize = 256;
          analyserRef.current = analyser;
          source.connect(analyser);

          const processor = audioContext.createScriptProcessor(BUFFER_SIZE, 1, 1);
          processorRef.current = processor;

          processor.onaudioprocess = (e) => {
            if (ws.readyState !== WebSocket.OPEN) return;
            const inputData = e.inputBuffer.getChannelData(0);
            const downsampled = downsampleBuffer(inputData, audioContext.sampleRate, TARGET_SAMPLE_RATE);
            const pcm16 = convertFloat32ToInt16(downsampled);
            ws.send(pcm16.buffer);
          };

          source.connect(processor);
          processor.connect(audioContext.destination);

          setStatus('Call in progress');
          setCallState('active');

          timerRef.current = setInterval(() => setElapsed(p => p + 1), 1000);
          animFrameRef.current = requestAnimationFrame(updateAudioLevel);

        } catch (err) {
          console.error('Microphone error:', err);
          setStatus('Microphone access denied');
          setCallState('ready');
          ws.close();
        }
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.session_id) {
          sessionIdRef.current = data.session_id;
          connectDashboardWs(data.session_id);
        }
      };

      ws.onclose = () => {
        if (callState === 'active') endCall();
      };

      ws.onerror = () => {
        setStatus('Connection error');
        setCallState('ready');
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Start call error:', err);
      setStatus('Error starting call');
      setCallState('ready');
    }
  };

  const connectDashboardWs = (sessionId: string) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsUrl = apiUrl.replace(/^http/, 'ws') + '/ws';
    const dws = new WebSocket(wsUrl);

    dws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'transcript' && msg.data.session_id === sessionId) {
          setTranscripts(prev => {
            const exists = prev.some(t => t.text === msg.data.text && t.time === msg.data.timestamp);
            if (exists) return prev;
            return [...prev, { text: msg.data.text, time: msg.data.timestamp }];
          });
        }
      } catch { /* ignore */ }
    };

    dashWsRef.current = dws;
  };

  const endCall = () => {
    if (processorRef.current && sourceRef.current) {
      sourceRef.current.disconnect();
      processorRef.current.disconnect();
    }
    if (audioContextRef.current) { audioContextRef.current.close(); audioContextRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    if (dashWsRef.current) { dashWsRef.current.close(); dashWsRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    analyserRef.current = null;
    setAudioLevel(0);
    setCallState('ended');
    setStatus('Call ended');
  };

  useEffect(() => {
    return () => {
      if (callState === 'active') endCall();
    };
  }, [callState]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  const waveformBars = 24;

  return (
    <div className="caller">
      <div className="caller-card">
        {/* Header */}
        <div className="caller-header">
          <Radio size={18} />
          <span>911 Simulator</span>
        </div>

        {/* Status Circle */}
        <div className={`caller-circle ${callState}`}>
          {callState === 'active' ? (
            <div className="caller-circle-inner">
              <span className="caller-timer">{formatTime(elapsed)}</span>
              <span className="caller-timer-label">Call Duration</span>
            </div>
          ) : callState === 'connecting' ? (
            <div className="caller-circle-inner">
              <span className="caller-connecting-spinner" />
              <span className="caller-timer-label">Connecting...</span>
            </div>
          ) : callState === 'ended' ? (
            <div className="caller-circle-inner">
              <PhoneOff size={28} />
              <span className="caller-timer-label">Call Ended</span>
            </div>
          ) : (
            <div className="caller-circle-inner">
              <Phone size={28} />
              <span className="caller-timer-label">Ready</span>
            </div>
          )}
        </div>

        {/* Waveform */}
        {callState === 'active' && (
          <div className="caller-waveform">
            {Array.from({ length: waveformBars }).map((_, i) => {
              const distance = Math.abs(i - waveformBars / 2) / (waveformBars / 2);
              const height = Math.max(4, audioLevel * 40 * (1 - distance * 0.7) + Math.random() * 4);
              return <div key={i} className="caller-waveform-bar" style={{ height }} />;
            })}
          </div>
        )}

        {/* Status */}
        <div className={`caller-status ${callState}`}>{status}</div>

        {/* Controls */}
        <div className="caller-controls">
          {callState === 'active' ? (
            <Button variant="danger" size="lg" icon={<PhoneOff size={18} />} onClick={endCall} fullWidth>
              End Call
            </Button>
          ) : (
            <Button
              variant="success"
              size="lg"
              icon={callState === 'connecting' ? undefined : <Phone size={18} />}
              loading={callState === 'connecting'}
              onClick={startCall}
              disabled={callState === 'connecting'}
              fullWidth
            >
              {callState === 'ended' ? 'Call Again' : 'Call 911'}
            </Button>
          )}
        </div>

        {/* Live Transcript */}
        {transcripts.length > 0 && (
          <div className="caller-transcript">
            <div className="caller-transcript-header">
              <Mic size={12} />
              <span>Live Transcript</span>
            </div>
            <div className="caller-transcript-list">
              {transcripts.map((t, i) => (
                <div key={i} className="caller-transcript-item">
                  <span className="caller-transcript-time">
                    {new Date(t.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <span className="caller-transcript-text">{t.text}</span>
                </div>
              ))}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Caller;
