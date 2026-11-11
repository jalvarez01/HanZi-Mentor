import { useTranslation } from 'react-i18next';
import { useAsync } from '../hooks/useAsync';
import { obtenerEjemplos } from '../services/api';
import './EjemplosCaracter.css';

const TATOEBA = 'https://tatoeba.org';

/**
 * Oraciones de ejemplo de un carácter (T27): consume ejemplos-flask, que las
 * trae de Tatoeba con el patrón Adapter.
 *
 * Se vuelven a pedir al cambiar de carácter o de idioma, porque la traducción
 * depende del idioma elegido. Si el servicio o Tatoeba no responden, el panel
 * lo avisa y deja reintentar sin afectar al resto de la página.
 */
export default function EjemplosCaracter({ hanzi }) {
  const { t, i18n } = useTranslation();
  const idioma = i18n.resolvedLanguage;

  const { datos, cargando, error, recargar } = useAsync(
    () => obtenerEjemplos(hanzi),
    [hanzi, idioma],
    Boolean(hanzi),
  );

  // Al cambiar rápido de carácter puede llegar tarde la respuesta del anterior.
  const vigentes = datos?.hanzi === hanzi ? datos : null;
  const ejemplos = vigentes?.ejemplos ?? [];

  return (
    <section className="hm-panel ejemplos" aria-labelledby="ejemplos-titulo">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('examples.kicker')}</span>
          <h2 id="ejemplos-titulo">
            {t('examples.title')} <span lang="zh-Hans">{hanzi}</span>
          </h2>
        </div>
      </div>

      {cargando && (
        <p className="hm-status hm-status--loading" role="status">{t('examples.loading')}</p>
      )}

      {!cargando && error && (
        <div className="hm-status hm-status--empty ejemplos-aviso" role="status">
          <span>{t('examples.unavailable')}</span>
          <button type="button" className="hm-btn" onClick={recargar}>
            {t('examples.retry')}
          </button>
        </div>
      )}

      {!cargando && !error && vigentes && ejemplos.length === 0 && (
        <p className="hm-status hm-status--empty">{t('examples.empty')}</p>
      )}

      {!cargando && !error && ejemplos.length > 0 && (
        <>
          <ul className="ejemplos-lista">
            {ejemplos.map((ejemplo) => (
              <li key={ejemplo.texto} className="ejemplo">
                <p className="ejemplo__texto" lang="zh-Hans">{ejemplo.texto}</p>
                {ejemplo.pinyin && <p className="ejemplo__pinyin">{ejemplo.pinyin}</p>}
                <p className="ejemplo__traduccion">
                  {ejemplo.traduccion || t('examples.noTranslation')}
                </p>
              </li>
            ))}
          </ul>

          {vigentes.atribucion && (
            <p className="ejemplos-credito">
              <a href={TATOEBA} target="_blank" rel="noopener noreferrer">
                {vigentes.atribucion}
              </a>
            </p>
          )}
        </>
      )}
    </section>
  );
}
