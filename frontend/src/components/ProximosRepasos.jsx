import { useTranslation } from 'react-i18next';
import { useAsync } from '../hooks/useAsync';
import { useFormato } from '../i18n/formato';
import { obtenerRepasos } from '../services/api';
import './ProximosRepasos.css';

/**
 * Sección "Próximos repasos" de Progreso (RF-IA-02).
 *
 * Hace su propia petición a progreso-flask (GET .../repasos/), como
 * PatronesError: si falla, muestra su error con "Reintentar" y el resto de
 * la página sigue igual. Cuando `recarga` cambia (el botón "Actualizar" de
 * la página), vuelve a pedir.
 *
 * Tres grupos, en este orden, y un grupo vacío no se muestra:
 * - Vencidos: los que el servicio da como vencidos;
 * - Hoy: los que vencen más tarde en el día de hoy (zona del navegador);
 * - Próximos N días: el resto, hasta los `dias` que devuelve el servicio.
 */
export default function ProximosRepasos({ usuarioId, recarga = 0 }) {
  const { t } = useTranslation();
  const formato = useFormato();
  const { datos, cargando, error, recargar } = useAsync(
    () => obtenerRepasos(usuarioId),
    [usuarioId, recarga],
    Boolean(usuarioId),
  );

  const proximos = datos?.proximos || [];
  const grupos = [
    { id: 'vencidos', titulo: t('progress.reviewsOverdue'), filas: datos?.vencidos || [], vencido: true },
    {
      id: 'hoy',
      titulo: t('progress.reviewsToday'),
      filas: proximos.filter((r) => formato.diasDeCalendario(r.proximo_repaso) <= 0),
    },
    {
      id: 'proximos',
      titulo: t('progress.reviewsNext', { count: datos?.dias ?? 7 }),
      filas: proximos.filter((r) => formato.diasDeCalendario(r.proximo_repaso) >= 1),
    },
  ].filter((g) => g.filas.length > 0);

  return (
    <section className="hm-panel progreso-bloque" aria-labelledby="progreso-repasos">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('progress.reviewKicker')}</span>
          <h2 id="progreso-repasos">{t('progress.reviewsTitle')}</h2>
        </div>
      </div>

      {error ? (
        <>
          <p className="hm-status hm-status--error" role="alert">{t('progress.reviewsError')}</p>
          <button type="button" className="hm-btn repasos-reintentar" onClick={recargar} disabled={cargando}>
            {t('common.retry')}
          </button>
        </>
      ) : !datos ? (
        <p className="hm-status hm-status--loading" role="status">{t('progress.loading')}</p>
      ) : grupos.length === 0 ? (
        <p className="hm-status hm-status--empty">{t('progress.reviewsEmpty', { count: datos.dias })}</p>
      ) : (
        grupos.map((g) => (
          <div key={g.id} className="repasos-grupo" data-grupo={g.id}>
            <h3 className="repasos-grupo__titulo" id={`repasos-${g.id}`}>{g.titulo}</h3>
            <ul className="repasos" aria-labelledby={`repasos-${g.id}`}>
              {g.filas.map((r) => (
                <li key={r.caracter} className="repaso">
                  <span className="repaso__hanzi" lang="zh">{r.caracter}</span>
                  <span className={g.vencido ? 'repaso__cuando repaso__cuando--vencido' : 'repaso__cuando'}>
                    {formato.repaso(r.proximo_repaso)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
