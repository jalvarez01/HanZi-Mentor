import { useTranslation } from 'react-i18next';
import TopBar from '../components/TopBar';
import { useProgreso } from '../hooks/useProgreso';
import { useFormato } from '../i18n/formato';
import './Progreso.css';

export default function Progreso() {
  // Mismo estado que el TopBar: una sola petición, misma recarga y mismo usuario.
  const { datos, cargando, error, recargar, usuarioId, reiniciar } = useProgreso();
  const { t } = useTranslation();
  const formato = useFormato();

  return (
    <>
      <TopBar title={t('progress.title')} />

      <div className="hm-page progreso">
        {error && <p className="hm-status hm-status--error" role="alert">{error}</p>}
        {cargando && <p className="hm-status hm-status--loading" role="status">{t('progress.loading')}</p>}

        {datos && (
          <>
            <div className="progreso-metricas">
              <Metrica
                valor={formato.porcentaje(datos.tasa_acierto)}
                etiqueta={t('progress.accuracy')}
                tono="jade"
              />
              <Metrica valor={datos.total_dominados} etiqueta={t('progress.mastered')} tono="ochre" />
              <Metrica
                valor={datos.total_por_reforzar}
                etiqueta={t('progress.toReinforce')}
                tono="cinnabar"
              />
            </div>

            <Bloque kicker={t('progress.levelKicker')} titulo={t('progress.levelTitle')} id="progreso-nivel">
              <ol className="progreso-niveles">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <li
                    key={n}
                    className={`progreso-nivel ${n <= datos.nivel_max_desbloqueado ? 'is-abierto' : ''} ${
                      n === datos.nivel_hsk ? 'is-actual' : ''
                    }`}
                    aria-current={n === datos.nivel_hsk ? 'step' : undefined}
                  >
                    HSK{n}
                  </li>
                ))}
              </ol>
              <p className="progreso-pie">
                {t('progress.levelSummary', {
                  nivel: datos.nivel_hsk,
                  maximo: datos.nivel_max_desbloqueado,
                })}
              </p>
            </Bloque>

            <Bloque kicker={t('progress.weakKicker')} titulo={t('progress.weakTitle')} id="progreso-debiles">
              {datos.caracteres_debiles.length === 0 ? (
                <p className="hm-status hm-status--empty">{t('progress.weakEmpty')}</p>
              ) : (
                <ul className="progreso-debiles">
                  {datos.caracteres_debiles.map((d) => (
                    <li key={d.caracter} className="progreso-debil">
                      <span className="progreso-debil__hanzi" lang="zh-Hans">{d.caracter}</span>
                      <div className="progreso-debil__barra" aria-hidden="true">
                        <div
                          className="progreso-debil__relleno"
                          style={{ width: `${Math.min(100, d.fallos * 15)}%` }}
                        />
                      </div>
                      <span className="progreso-debil__cuenta">
                        {t('progress.failures', { count: d.fallos })}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Bloque>

            <Bloque kicker={t('progress.masteredKicker')} titulo={t('progress.mastered')} id="progreso-dominados">
              {datos.caracteres_dominados.length === 0 ? (
                <p className="hm-status hm-status--empty">{t('progress.masteredEmpty')}</p>
              ) : (
                <ul className="progreso-chips">
                  {datos.caracteres_dominados.map((c) => (
                    <li key={c} className="progreso-chip" lang="zh-Hans">{c}</li>
                  ))}
                </ul>
              )}
            </Bloque>

            <Bloque kicker={t('progress.reviewKicker')} titulo={t('progress.reviewTitle')} id="progreso-repaso">
              <p className="progreso-pie">
                {datos.proximo_repaso
                  ? formato.fechaHora(datos.proximo_repaso)
                  : t('progress.reviewNone')}
              </p>
            </Bloque>

            <div className="progreso-acciones">
              <button type="button" className="hm-btn hm-btn--block" onClick={recargar}>
                {t('progress.refresh')}
              </button>
              <button type="button" className="progreso-reiniciar" onClick={reiniciar}>
                {t('progress.newUser')}
              </button>
            </div>

            <p className="progreso-id">{t('progress.userId', { id: usuarioId })}</p>
          </>
        )}
      </div>
    </>
  );
}

function Metrica({ valor, etiqueta, tono }) {
  return (
    <div className={`progreso-metrica progreso-metrica--${tono}`}>
      <span className="progreso-metrica__valor">{valor}</span>
      <span className="progreso-metrica__etiqueta">{etiqueta}</span>
    </div>
  );
}

function Bloque({ kicker, titulo, id, children }) {
  return (
    <section className="hm-panel progreso-bloque" aria-labelledby={id}>
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{kicker}</span>
          <h2 id={id}>{titulo}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}
