import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { mejorRacha, useProgreso } from '../hooks/useProgreso';
import { IconoAtras, IconoLlama } from './Iconos';
import SelectorIdioma from './SelectorIdioma';
import './TopBar.css';

export default function TopBar({ title, back = false }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <header className="topbar">
      <div className="topbar-marca">
        {back ? (
          <button
            type="button"
            className="hm-btn-icon topbar-atras"
            onClick={() => navigate(-1)}
            aria-label={t('topbar.back')}
          >
            <IconoAtras />
          </button>
        ) : (
          <span className="hm-seal" aria-hidden="true">学</span>
        )}

        <div className="topbar-nombre">
          <strong>{t('app.name')}</strong>
          {title ? <h1>{title}</h1> : <span>{t('app.tagline')}</span>}
        </div>
      </div>

      <div className="topbar-acciones">
        <MejorRacha />
        <SelectorIdioma />
      </div>
    </header>
  );
}

function MejorRacha() {
  const { t } = useTranslation();
  const { datos, cargando, error } = useProgreso();

  let valor = '…';
  let etiqueta = t('topbar.streakLoading');

  if (error) {
    valor = '—';
    etiqueta = t('topbar.streakUnavailable');
  } else if (datos && !cargando) {
    valor = mejorRacha(datos);
    etiqueta = t('topbar.streak', { count: valor });
  }

  return (
    <span className="topbar-racha" role="img" aria-label={etiqueta} title={etiqueta}>
      <IconoLlama />
      <span aria-hidden="true">{valor}</span>
    </span>
  );
}
