import { useTranslation } from 'react-i18next';
import { useReporte } from '../hooks/useReporte';
import { useFormato } from '../i18n/formato';
import './ReporteProgreso.css';

/**
 * Reporte de progreso asíncrono (T20): lo pide a reportes-flask, que lo
 * encola en Redis para un worker de Celery, y consulta su estado hasta que
 * está listo. Mientras tanto se puede seguir usando la app.
 */
export default function ReporteProgreso({ usuarioId }) {
  const { t } = useTranslation();
  const formato = useFormato();
  const { estado, resultado, error, generar } = useReporte(usuarioId);
  const generando = estado === 'pendiente' || estado === 'en_proceso';

  function descargar() {
    const archivo = new Blob([JSON.stringify(resultado, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(archivo);
    // Fecha local para el nombre: generado_en viene en UTC y de noche en
    // Colombia ya es el día siguiente.
    const fecha = new Date(resultado.generado_en);
    const dia = [
      fecha.getFullYear(),
      String(fecha.getMonth() + 1).padStart(2, '0'),
      String(fecha.getDate()).padStart(2, '0'),
    ].join('-');
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = `reporte-hanzimentor-${dia}.json`;
    enlace.click();
    URL.revokeObjectURL(url);
  }

  let textoBoton = t('report.generate');
  if (estado === 'listo') textoBoton = t('report.again');
  if (estado === 'error') textoBoton = t('report.retry');

  return (
    <section className="hm-panel reporte" aria-labelledby="reporte-titulo">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('report.kicker')}</span>
          <h2 id="reporte-titulo">{t('report.title')}</h2>
        </div>
      </div>

      <p className="reporte-texto">{t('report.description')}</p>

      {generando && (
        <p className="hm-status hm-status--loading" role="status">
          {estado === 'pendiente' ? t('report.queued') : t('report.generating')}
        </p>
      )}

      {estado === 'error' && (
        <p className="hm-status hm-status--error" role="alert">{error}</p>
      )}

      {estado === 'listo' && resultado && (
        <dl className="reporte-resumen" aria-live="polite">
          <div>
            <dt>{t('report.generatedAt')}</dt>
            <dd>{formato.fechaHora(resultado.generado_en)}</dd>
          </div>
          <div>
            <dt>{t('progress.levelTitle')}</dt>
            <dd>HSK{resultado.nivel_hsk}</dd>
          </div>
          <div>
            <dt>{t('progress.accuracy')}</dt>
            <dd>{formato.porcentaje(resultado.tasa_acierto)}</dd>
          </div>
          <div>
            <dt>{t('progress.mastered')}</dt>
            <dd>{resultado.total_dominados}</dd>
          </div>
          <div>
            <dt>{t('progress.toReinforce')}</dt>
            <dd>{resultado.total_por_reforzar}</dd>
          </div>
        </dl>
      )}

      <div className="reporte-acciones">
        {estado === 'listo' && resultado && (
          <button type="button" className="hm-btn hm-btn--jade" onClick={descargar}>
            {t('report.download')}
          </button>
        )}
        <button type="button" className="hm-btn" onClick={generar} disabled={generando}>
          {textoBoton}
        </button>
      </div>
    </section>
  );
}
