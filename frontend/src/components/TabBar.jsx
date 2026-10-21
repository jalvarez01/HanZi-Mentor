import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { IconoInicio, IconoPracticar, IconoProgreso, IconoTrazos } from './Iconos';
import './TabBar.css';

const TABS = [
  { to: '/', clave: 'nav.home', Icono: IconoInicio },
  { to: '/trazos', clave: 'nav.strokes', Icono: IconoTrazos },
  { to: '/practica', clave: 'nav.practice', Icono: IconoPracticar },
  { to: '/progreso', clave: 'nav.progress', Icono: IconoProgreso },
];

export default function TabBar() {
  const { t } = useTranslation();

  return (
    <nav className="tabbar" aria-label={t('nav.label')}>
      {TABS.map(({ to, clave, Icono }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) => `tab ${isActive ? 'is-active' : ''}`}
        >
          <Icono className="tab-icono" />
          <span className="tab-label">{t(clave)}</span>
        </NavLink>
      ))}
    </nav>
  );
}
