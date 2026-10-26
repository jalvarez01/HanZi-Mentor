import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import TopBar from '../components/TopBar';
import { useUsuario } from '../hooks/useUsuario';
import { useFormato } from '../i18n/formato';
import { crearSesion, responderEjercicio, generarLeccion } from '../services/api';
import './Practica.css';

const NIVELES = [1, 2, 3, 4, 5, 6];
const NUMERALES = ['一', '二', '三', '四', '五', '六'];

export default function Practica() {
  const { usuarioId } = useUsuario();
  const { t } = useTranslation();
  const formato = useFormato();

  const [modo, setModo] = useState('sesion'); // 'sesion' (sesiones-flask) | 'leccion' (catalogo-flask)

  const [sesion, setSesion] = useState(null);
  const [indice, setIndice] = useState(0);
  const [ultimoResultado, setUltimoResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);
  const [terminada, setTerminada] = useState(false);

  const [leccion, setLeccion] = useState(null);
  const [indiceLeccion, setIndiceLeccion] = useState(0);

  const ejercicio = sesion?.ejercicios?.[indice];
  const ejercicioLeccion = leccion?.ejercicios?.[indiceLeccion];

  async function empezarLeccion(nivel) {
    setCargando(true);
    setError(null);

    try {
      const nueva = await generarLeccion({ usuarioId, nivelHsk: nivel });
      setLeccion(nueva);
      setIndiceLeccion(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }

  async function empezar(nivel) {
    setCargando(true);
    setError(null);
    setTerminada(false);
    setUltimoResultado(null);

    try {
      const nueva = await crearSesion({ usuarioId, nivelHsk: nivel });
      setSesion(nueva);
      setIndice(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }

  async function responder(acerto) {
    setCargando(true);
    setError(null);

    try {
      const resultado = await responderEjercicio(ejercicio.id, acerto);
      setUltimoResultado({ ...resultado, acerto });

      if (resultado.sesion_completada) {
        setTerminada(true);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }

  function siguiente() {
    setUltimoResultado(null);
    setIndice((i) => i + 1);
  }

  // Sin progreso (respuesta con `aviso`) la tasa llega en null: no se pinta como 0 %.
  const tasaAcierto = (tasa) => (tasa == null ? t('practice.notAvailable') : formato.porcentaje(tasa));

  const tipoEjercicio = (tipo) =>
    tipo === 'trazo' ? t('practice.typeStrokes') : t('practice.typeMeaning');

  // ---------------------------------------------------------- sin sesión

  if (!sesion && !leccion) {
    return (
      <>
        <TopBar title={t('practice.title')} />
        <div className="hm-page practica">
          <div className="practica-modos" role="group" aria-label={t('practice.modeLabel')}>
            <button
              type="button"
              className="practica-modo"
              aria-pressed={modo === 'sesion'}
              onClick={() => setModo('sesion')}
            >
              {t('practice.modeSession')}
            </button>
            <button
              type="button"
              className="practica-modo"
              aria-pressed={modo === 'leccion'}
              onClick={() => setModo('leccion')}
            >
              {t('practice.modeLesson')}
            </button>
          </div>

          <section className="hm-panel practica-panel" aria-labelledby="practica-niveles-titulo">
            <div className="hm-section-head">
              <div>
                <span className="hm-kicker">{t('practice.levelKicker')}</span>
                <h2 id="practica-niveles-titulo">{t('practice.levelTitle')}</h2>
              </div>
            </div>

            <p className="practica-intro">
              {modo === 'sesion' ? t('practice.introSession') : t('practice.introLesson')}
            </p>

            {error && <p className="hm-status hm-status--error" role="alert">{error}</p>}

            <div className="practica-niveles">
              {NIVELES.map((n) => (
                <button
                  key={n}
                  type="button"
                  className="practica-nivel"
                  disabled={cargando}
                  onClick={() => (modo === 'sesion' ? empezar(n) : empezarLeccion(n))}
                >
                  <span className="practica-nivel__numeral" lang="zh-Hans" aria-hidden="true">
                    {NUMERALES[n - 1]}
                  </span>
                  <span>HSK {n}</span>
                </button>
              ))}
            </div>

            {cargando && (
              <p className="hm-status hm-status--loading" role="status">
                {modo === 'sesion' ? t('practice.buildingSession') : t('practice.buildingLesson')}
              </p>
            )}

            {modo === 'sesion' && <p className="practica-nota">{t('practice.lockedNote')}</p>}
          </section>
        </div>
      </>
    );
  }

  // -------------------------------------------------------------- lección

  if (leccion) {
    if (!ejercicioLeccion) {
      return (
        <>
          <TopBar title={t('practice.lessonDoneBar')} />
          <div className="hm-page practica practica-resumen">
            <span className="hm-seal hm-seal--lg" aria-hidden="true">完</span>
            <h2>{t('practice.lessonDoneTitle')}</h2>
            <p className="practica-intro">
              {t('practice.lessonDoneText', {
                count: leccion.ejercicios.length,
                nivel: leccion.nivel_hsk,
              })}
            </p>
            <button
              type="button"
              className="hm-btn"
              onClick={() => { setLeccion(null); setIndiceLeccion(0); }}
            >
              {t('practice.anotherLesson')}
            </button>
          </div>
        </>
      );
    }

    return (
      <>
        <TopBar title={t('practice.lessonBar', { nivel: leccion.nivel_hsk })} />
        <div className="hm-page practica">
          <Avance actual={indiceLeccion} total={leccion.ejercicios.length} />

          <article className="hm-card practica-tarjeta">
            <span className="hm-kicker">{tipoEjercicio(ejercicioLeccion.tipo)}</span>
            <div className="practica-hanzi" lang="zh-Hans">{ejercicioLeccion.caracter.hanzi}</div>
            <p className="practica-dato">
              {ejercicioLeccion.caracter.pinyin} · {ejercicioLeccion.caracter.definicion}
            </p>
          </article>

          {ejercicioLeccion.tipo === 'trazo' && (
            <Link to={`/trazos?caracter=${ejercicioLeccion.caracter.hanzi}`} className="practica-enlace">
              {t('practice.seeStrokes')}
            </Link>
          )}

          <button
            type="button"
            className="hm-btn hm-btn--block practica-siguiente"
            onClick={() => setIndiceLeccion((i) => i + 1)}
          >
            {t('practice.next')}
          </button>
        </div>
      </>
    );
  }

  // ------------------------------------------------------- sesión completa

  if (terminada) {
    const correctas = sesion.ejercicios.length;
    return (
      <>
        <TopBar title={t('practice.sessionDoneBar')} />
        <div className="hm-page practica practica-resumen">
          <span className="hm-seal hm-seal--lg" aria-hidden="true">完</span>
          <h2>{t('practice.sessionDoneTitle')}</h2>
          <p className="practica-intro">
            {t('practice.sessionDoneText', { count: correctas, nivel: sesion.nivel_hsk })}
          </p>

          {ultimoResultado?.aviso && (
            <p className="hm-status hm-status--empty" role="status">{t('practice.progressNotSaved')}</p>
          )}

          {ultimoResultado && (
            <p className="practica-dato">
              {t('practice.currentAccuracy')}{' '}
              <strong>{tasaAcierto(ultimoResultado.tasa_acierto)}</strong>
            </p>
          )}

          <button type="button" className="hm-btn" onClick={() => setSesion(null)}>
            {t('practice.anotherSession')}
          </button>
          <Link to="/progreso" className="practica-enlace">{t('practice.seeProgress')}</Link>
        </div>
      </>
    );
  }

  // -------------------------------------------------------- ejercicio actual

  return (
    <>
      <TopBar
        title={t('practice.sessionBar', { nivel: sesion.nivel_hsk, dificultad: sesion.dificultad })}
      />

      <div className="hm-page practica">
        <Avance actual={indice} total={sesion.ejercicios.length}>
          {ejercicio?.es_refuerzo && (
            <span className="practica-refuerzo">{t('practice.reinforcement')}</span>
          )}
        </Avance>

        {error && <p className="hm-status hm-status--error" role="alert">{error}</p>}

        <article className="hm-card practica-tarjeta">
          <span className="hm-kicker">{tipoEjercicio(ejercicio?.tipo)}</span>
          <div className="practica-hanzi" lang="zh-Hans">{ejercicio?.caracter}</div>
        </article>

        {!ultimoResultado ? (
          <>
            <p className="practica-pregunta">{t('practice.question')}</p>
            <div className="practica-acciones">
              <button
                type="button"
                className="hm-btn"
                disabled={cargando}
                onClick={() => responder(false)}
              >
                {t('practice.failed')}
              </button>
              <button
                type="button"
                className="hm-btn hm-btn--jade"
                disabled={cargando}
                onClick={() => responder(true)}
              >
                {t('practice.correct')}
              </button>
            </div>
            {ejercicio?.tipo === 'trazo' && (
              <Link to={`/trazos?caracter=${ejercicio.caracter}`} className="practica-enlace">
                {t('practice.seeStrokes')}
              </Link>
            )}
          </>
        ) : (
          <div className="hm-panel practica-feedback" role="status">
            <p className={ultimoResultado.acerto ? 'practica-ok' : 'practica-fallo'}>
              {ultimoResultado.acerto ? t('practice.feedbackCorrect') : t('practice.feedbackFailed')}
            </p>
            {ultimoResultado.aviso && (
              <p className="hm-status hm-status--empty">{t('practice.progressNotSaved')}</p>
            )}
            <p className="practica-dato">
              {t('practice.nextReview')}{' '}
              <strong>{formato.relativo(ultimoResultado.proximo_repaso) ?? t('practice.notAvailable')}</strong>
            </p>
            <p className="practica-dato">
              {t('practice.accuracy')}{' '}
              <strong>{tasaAcierto(ultimoResultado.tasa_acierto)}</strong>
            </p>

            <button type="button" className="hm-btn hm-btn--block practica-siguiente" onClick={siguiente}>
              {t('practice.next')}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

/** Barra de avance y contador "n de m" (con contenido extra opcional, p. ej. la etiqueta de refuerzo). */
function Avance({ actual, total, children }) {
  const { t } = useTranslation();

  return (
    <>
      <div
        className="practica-barra"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={actual}
        aria-label={t('practice.progressLabel')}
      >
        <div className="practica-barra__relleno" style={{ width: `${(actual / total) * 100}%` }} />
      </div>
      <p className="practica-contador">
        {t('practice.counter', { actual: actual + 1, total })}
        {children}
      </p>
    </>
  );
}
