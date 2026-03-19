import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Headset, Phone, RotateCcw, Archive, Play } from 'lucide-react';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useDispatchTest } from '../contexts/DispatchTestContext';
import './NavBar.css';

const NAV_LINKS = [
  { to: '/caller', label: 'Caller', icon: Phone },
  { to: '/call-taker', label: 'Call Taker', icon: Headset },
  { to: '/', label: 'Dispatcher', icon: LayoutDashboard },
  { to: '/past-cases', label: 'Past Cases', icon: Archive },
] as const;

export default function NavBar() {
  const { connected } = useWebSocket();
  const {
    phase, createdCount, dispatchedCount, manualMode, toggleManualMode,
    startTest, testLocked, currentRound,
  } = useDispatchTest();
  const [resetting, setResetting] = useState(false);
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const testActive = phase === 'round_running' || phase === 'round_waiting' || phase === 'resetting' || phase === 'tlx';

  const handleReset = async () => {
    if (!window.confirm('Reset all data? This will clear all calls, cases, and dispatch state.')) return;
    setResetting(true);
    try {
      const res = await fetch(`${apiUrl}/admin/reset`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
      console.error('Reset failed:', err);
      alert('Failed to reset system. Check console for details.');
    } finally {
      setResetting(false);
    }
  };

  return (
    <nav className="eras-navbar">
      <div className="eras-navbar-brand">
        <div className="eras-navbar-logo">E</div>
        <span className="eras-navbar-title">ERAS</span>
      </div>

      <div className="eras-navbar-links">
        {NAV_LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `eras-navbar-link ${isActive ? 'active' : ''}`}
          >
            <Icon size={15} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      <div className="eras-navbar-status">
        <button
          className={`eras-navbar-toggle${manualMode ? ' eras-navbar-toggle-on' : ''}${testLocked ? ' eras-navbar-toggle-locked' : ''}`}
          onClick={toggleManualMode}
          disabled={testLocked}
          title={testLocked ? 'Mode locked during test' : manualMode ? 'Switch to optimizer mode' : 'Switch to manual mode'}
        >
          <span className="eras-navbar-toggle-track">
            <span className="eras-navbar-toggle-thumb" />
          </span>
          <span>Manual</span>
        </button>
        <button
          className="eras-navbar-reset"
          onClick={startTest}
          disabled={testActive}
          title="Start dispatch test"
        >
          <Play size={13} />
          <span>Start Test</span>
        </button>
        {testActive && (
          <span className="eras-navbar-test-progress">
            Round {currentRound}/2 · {createdCount}/6 created · {dispatchedCount}/6 dispatched
          </span>
        )}
        <button
          className={`eras-navbar-reset${resetting ? ' resetting' : ''}`}
          onClick={handleReset}
          disabled={resetting || testActive}
          title="Reset all data"
        >
          <RotateCcw size={13} className={resetting ? 'spin' : ''} />
          <span>{resetting ? 'Resetting…' : 'Reset'}</span>
        </button>
        <span className={`eras-navbar-dot ${connected ? 'online' : 'offline'}`} />
        <span className="eras-navbar-status-label">
          {connected ? 'Online' : 'Offline'}
        </span>
      </div>
    </nav>
  );
}
