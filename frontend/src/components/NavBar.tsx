import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Headset, Phone } from 'lucide-react';
import { useWebSocket } from '../contexts/WebSocketContext';
import './NavBar.css';

const NAV_LINKS = [
  { to: '/caller', label: 'Caller', icon: Phone },
  { to: '/call-taker', label: 'Call Taker', icon: Headset },
  { to: '/', label: 'Dispatcher', icon: LayoutDashboard },
] as const;

export default function NavBar() {
  const { connected } = useWebSocket();

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
        <span className={`eras-navbar-dot ${connected ? 'online' : 'offline'}`} />
        <span className="eras-navbar-status-label">
          {connected ? 'Online' : 'Offline'}
        </span>
      </div>
    </nav>
  );
}
