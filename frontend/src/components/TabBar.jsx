import { NavLink } from 'react-router-dom';
import './TabBar.css';

const TABS = [
  { to: '/', label: 'Inicio', glyph: '家' },
  { to: '/trazos', label: 'Trazos', glyph: '写' },
  { to: '/tutor', label: 'Tutor', glyph: '师' },
  { to: '/progreso', label: 'Progreso', glyph: '级' },
];

export default function TabBar() {
  return (
    <nav className="tabbar">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.to === '/'}
          className={({ isActive }) => `tab ${isActive ? 'is-active' : ''}`}
        >
          <span className="tab-glyph">{t.glyph}</span>
          <span className="tab-label">{t.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
