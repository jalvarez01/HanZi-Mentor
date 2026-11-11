import { useTranslation } from 'react-i18next';
import { useAsync } from '../hooks/useAsync';
import { useFormato } from '../i18n/formato';
import { obtenerPatrones } from '../services/api';
import './PatronesError.css';

/**
 * Sección "Tus patrones de error" de Progreso (RF-IA-01).
 *
 * Hace su propia petición a progreso-flask (GET .../patrones/): si falla,
 * muestra su error con "Reintentar" y el resto de la página sigue igual.
 * `titulo` y `consejo` llegan ya traducidos; `codigo` no cambia con el idioma.
 * Cuando `recarga` cambia (el botón "Actualizar" de la página), vuelve a pedir.
 */
export default function PatronesError({ usuarioId, recarga = 0 }) {
  const { t } = useTranslation();
  const formato = useFormato();
  const { datos, cargando, error, recargar } = useAsync(
    () => obtenerPatrones(usuarioId),
    [usuarioId, recarga],
    Boolean(usuarioId),
  );

  const patrones = datos?.patrones || [];

  return (
    <section className="hm-panel progreso-bloque" aria-labelledby="progreso-patrones">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('progress.patternsKicker')}</span>
          <h2 id="progreso-patrones">{t('progress.patternsTitle')}</h2>
        </div>
      </div>

      {error ? (
        <>
          <p className="hm-status hm-status--error" role="alert">{t('progress.patternsError')}</p>
          <button type="button" className="hm-btn patrones-reintentar" onClick={recargar} disabled={cargando}>
            {t('common.retry')}
          </button>
        </>
      ) : !datos ? (
        <p className="hm-status hm-status--loading" role="status">{t('progress.loading')}</p>
      ) : patrones.length === 0 ? (
        <p className="hm-status hm-status--empty">{t('progress.patternsEmpty')}</p>
      ) : (
        <>
          <ul className="patrones">
            {patrones.map((p) => (
              <li key={p.codigo} className="patron" data-codigo={p.codigo}>
                <p className="patron__titulo">{p.titulo}</p>
                <p className="patron__consejo">{p.consejo}</p>
                {p.caracteres.length > 0 && (
                  <ul className="patron__caracteres" aria-label={t('progress.patternsCharacters')}>
                    {p.caracteres.map((c) => (
                      <li key={c} className="patron__caracter" lang="zh-Hans">{c}</li>
                    ))}
                  </ul>
                )}
                <p className="patron__meta">
                  <span>{t('progress.patternsTimes', { count: p.frecuencia })}</span>
                  <span>{t('progress.patternsLastTime', { cuando: formato.hace(p.ultima_vez) })}</span>
                </p>
              </li>
            ))}
          </ul>
          <p className="progreso-pie">{t('progress.patternsWindow', { count: datos.ventana_dias })}</p>
        </>
      )}
    </section>
  );
}
