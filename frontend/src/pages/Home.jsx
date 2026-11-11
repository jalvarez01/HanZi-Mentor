import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import TopBar from '../components/TopBar';
import {
  IconoCandado,
  IconoChevron,
  IconoDestello,
  IconoFlecha,
  IconoPlay,
} from '../components/Iconos';
import { useAsync } from '../hooks/useAsync';
import { useProgreso } from '../hooks/useProgreso';
import { listarCaracteres } from '../services/api';
import './Home.css';

const NIVELES = [1, 2, 3, 4, 5, 6];
const NUMERALES = ['一', '二', '三', '四', '五', '六'];
const COLORES_BALDOSA = ['', 'hm-tile--jade', 'hm-tile--red'];

// Cuántos caracteres del nivel se piden para elegir las palabras del día.
const MUESTRA_PALABRAS = 60;

export default function Home() {
  const { datos: progreso, cargando, error, recargar } = useProgreso();

  // Sin progreso (backend caído) las palabras del día salen de HSK 1.
  const nivel = progreso?.nivel_hsk ?? (error ? 1 : null);

  return (
    <>
      <TopBar />

      <main className="home">
        <Apertura />
        <FranjaCita />
        <LeccionHoy progreso={progreso} cargando={cargando} error={error} recargar={recargar} />
        <PalabrasDelDia nivel={nivel} />
        <MapaRuta progreso={progreso} cargando={cargando} error={error} recargar={recargar} />
      </main>
    </>
  );
}

// ------------------------------------------------------------------ apertura

function Apertura() {
  const { t } = useTranslation();

  return (
    <section className="home-apertura hm-panel">
      <div className="home-apertura__texto">
        <span className="hm-kicker">{t('home.opening.kicker')}</span>
        {/* El Inicio no pasa título al TopBar: este es el h1 de la página. */}
        <h1 className="home-apertura__titulo">
          {t('home.opening.line1')}
          <br />
          <i>{t('home.opening.line2')}</i>
          <br />
          <b>{t('home.opening.line3')}</b>
        </h1>
        <p>{t('home.opening.text')}</p>
        <Link to="/como-funciona" className="hm-btn">
          {t('home.opening.cta')} <IconoFlecha />
        </Link>
      </div>

      <div className="home-apertura__arte" role="img" aria-label={t('home.opening.artLabel')}>
        <div className="home-sol" />
        <div className="home-montana home-montana--fondo" />
        <div className="home-montana home-montana--frente" />
        <div className="home-muralla"><span /><span /><span /></div>
        <span className="home-arte-caracter" aria-hidden="true">写</span>
        <div className="home-sello-rojo" aria-hidden="true">
          初<br /><small>{t('home.opening.stamp')}</small>
        </div>
      </div>
    </section>
  );
}

// --------------------------------------------------------------- franja cita

function FranjaCita() {
  const { t } = useTranslation();

  return (
    <section className="home-cita">
      <span className="home-cita__comilla" aria-hidden="true">“</span>
      <p>
        {t('home.quote.text')}
        <br />
        <em>{t('home.quote.emphasis')}</em>
      </p>
      <span className="home-cita__sello" aria-hidden="true">道</span>
    </section>
  );
}

// ------------------------------------------------------------ lección de hoy

function LeccionHoy({ progreso, cargando, error, recargar }) {
  const { t } = useTranslation();
  const nivel = progreso?.nivel_hsk;

  return (
    <section className="home-seccion hm-panel" aria-labelledby="home-leccion-titulo">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('home.lesson.kicker')}</span>
          <h2 id="home-leccion-titulo">{t('home.lesson.title')}</h2>
        </div>
        {nivel && (
          <span className="hm-count" aria-label={t('home.lesson.countLabel', { nivel })}>
            {String(nivel).padStart(2, '0')} <i>/ 06</i>
          </span>
        )}
      </div>

      {error && (
        <EstadoError mensaje={t('home.lesson.error')} recargar={recargar} />
      )}

      {!error && (cargando || !progreso) && (
        <p className="hm-status hm-status--loading" role="status">{t('home.lesson.loading')}</p>
      )}

      {!error && progreso && !cargando && (
        <article className="home-destacada hm-card">
          <div className="home-destacada__imagen" aria-hidden="true">
            <div className="home-destacada__tejado" />
            <div className="home-destacada__sol" />
            <span>{NUMERALES[nivel - 1]}级</span>
          </div>
          <div className="home-destacada__contenido">
            <span className="hm-kicker">{t('home.lesson.cardKicker', { nivel })}</span>
            <h3>{t('home.lesson.cardTitle', { nivel })}</h3>
            <p>{t('home.lesson.cardText')}</p>
            <Link to="/practica" className="hm-btn">
              {t('home.lesson.start')} <IconoPlay />
            </Link>
          </div>
        </article>
      )}
    </section>
  );
}

// ----------------------------------------------------------- palabras del día

/**
 * Elige 3 caracteres de forma determinista según la fecha local: todos los
 * usuarios del mismo nivel ven las mismas palabras ese día y cambian a medianoche.
 */
function elegirPalabrasDelDia(caracteres, fecha = new Date()) {
  if (caracteres.length <= 3) return caracteres;

  const dia = Math.floor(
    Date.UTC(fecha.getFullYear(), fecha.getMonth(), fecha.getDate()) / 864e5,
  );
  const inicio = (dia * 3) % caracteres.length;

  return [0, 1, 2].map((i) => caracteres[(inicio + i) % caracteres.length]);
}

function PalabrasDelDia({ nivel }) {
  const { t } = useTranslation();
  const { datos, cargando, error, recargar } = useAsync(
    () => listarCaracteres({ nivel, limite: MUESTRA_PALABRAS }),
    [nivel],
    Boolean(nivel),
  );

  const palabras = elegirPalabrasDelDia(datos?.caracteres || []);
  const listo = nivel && datos && !cargando && !error;

  return (
    <section className="home-seccion hm-panel" aria-labelledby="home-palabras-titulo">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('home.words.kicker')}</span>
          <h2 id="home-palabras-titulo">{t('home.words.title')}</h2>
        </div>
        <IconoDestello className="home-destello" />
      </div>

      {error && <EstadoError mensaje={t('home.words.error')} recargar={recargar} />}

      {!error && !listo && (
        <p className="hm-status hm-status--loading" role="status">{t('home.words.loading')}</p>
      )}

      {listo && palabras.length === 0 && (
        <p className="hm-status hm-status--empty">{t('home.words.empty', { nivel })}</p>
      )}

      {listo && palabras.length > 0 && (
        <>
          <ul className="home-palabras">
            {palabras.map((c, i) => (
              <li key={c.hanzi}>
                <Link
                  to={`/trazos?caracter=${encodeURIComponent(c.hanzi)}`}
                  className={`hm-tile ${COLORES_BALDOSA[i % COLORES_BALDOSA.length]}`}
                >
                  <span className="hm-tile__hanzi" lang="zh-Hans">{c.hanzi}</span>
                  <span className="hm-tile__pinyin">{c.pinyin || '—'}</span>
                  <span className="hm-tile__meaning home-palabras__significado">
                    {c.definicion || '—'}
                  </span>
                  {/* El nombre accesible sale del texto visible más esta acción (WCAG 2.5.3) */}
                  <span className="home-sr">{t('home.words.tileAction')}</span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="home-nota">{t('home.words.note')}</p>
        </>
      )}
    </section>
  );
}

// -------------------------------------------------------------- mapa de ruta

function MapaRuta({ progreso, cargando, error, recargar }) {
  const { t } = useTranslation();
  const listo = progreso && !cargando && !error;

  function estadoNivel(n) {
    if (!listo) return 'pendiente';
    if (n === progreso.nivel_hsk) return 'actual';
    if (n > progreso.nivel_max_desbloqueado) return 'bloqueado';
    return 'abierto';
  }

  return (
    <section className="home-seccion hm-panel" aria-labelledby="home-mapa-titulo">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('home.map.kicker')}</span>
          <h2 id="home-mapa-titulo">{t('home.map.title')}</h2>
        </div>
        <Link to="/progreso" className="hm-btn-icon hm-btn-icon--sm" aria-label={t('home.map.more')}>
          <IconoChevron />
        </Link>
      </div>

      {error && <EstadoError mensaje={t('home.map.error')} recargar={recargar} />}

      {!error && !listo && (
        <p className="hm-status hm-status--loading" role="status">{t('home.map.loading')}</p>
      )}

      <div className="home-mapa">
        <div className="home-mapa__camino" aria-hidden="true"><i /><i /><i /><i /></div>

        <ol className="home-mapa__niveles" aria-label={t('home.map.listLabel')}>
          {NIVELES.map((n) => {
            const estado = estadoNivel(n);
            return (
              <li
                key={n}
                className={`home-mapa__nivel home-mapa__nivel--${n} is-${estado}`}
                aria-current={estado === 'actual' ? 'step' : undefined}
              >
                {estado === 'bloqueado' && <IconoCandado />}
                <span>HSK {n}</span>
                {estado !== 'pendiente' && (
                  <span className="home-sr">{t(`home.map.state.${estado}`)}</span>
                )}
              </li>
            );
          })}
        </ol>

        <span className="home-mapa__brujula" aria-hidden="true">东</span>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ estados

function EstadoError({ mensaje, recargar }) {
  const { t } = useTranslation();

  return (
    <div className="hm-status hm-status--error home-error" role="alert">
      <span>{mensaje}</span>
      <button type="button" className="home-error__reintentar" onClick={recargar}>
        {t('common.retry')}
      </button>
    </div>
  );
}
