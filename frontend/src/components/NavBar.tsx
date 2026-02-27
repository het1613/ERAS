import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Headset, Phone, RotateCcw } from 'lucide-react';
import { useWebSocket } from '../contexts/WebSocketContext';
import './NavBar.css';

const NAV_LINKS = [
  { to: '/caller', label: 'Caller', icon: Phone },
  { to: '/call-taker', label: 'Call Taker', icon: Headset },
  { to: '/', label: 'Dispatcher', icon: LayoutDashboard },
] as const;

export default function NavBar() {
  const { connected } = useWebSocket();
  const [resetting, setResetting] = useState(false);
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
          className={`eras-navbar-reset${resetting ? ' resetting' : ''}`}
          onClick={handleReset}
          disabled={resetting}
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
