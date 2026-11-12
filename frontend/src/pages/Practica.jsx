import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import CuadriculaHanzi from '../components/CuadriculaHanzi';
import { IconoCandado } from '../components/Iconos';
import PorQue from '../components/PorQue';
import RespuestaPinyin from '../components/RespuestaPinyin';
import TopBar from '../components/TopBar';
import { useSuscripcion } from '../hooks/useSuscripcion';
import { useUsuario } from '../hooks/useUsuario';
import { useFormato } from '../i18n/formato';
import {
  crearSesion,
  generarLeccion,
  obtenerCaracter,
  obtenerDesempeno,
  obtenerPatrones,
  precargarCaracter,
  responderEjercicio,
} from '../services/api';
import './Practica.css';

const NIVELES = [1, 2, 3, 4, 5, 6];
const NUMERALES = ['一', '二', '三', '四', '五', '六'];

export default function Practica() {
  const { usuarioId } = useUsuario();
  const { t } = useTranslation();
  // RF-USR-01: Free practica hasta HSK 3. Sin respuesta del servicio no se bloquea nada.
  const { suscripcion, nivelMaximo, sinConfirmar } = useSuscripcion(usuarioId);
  const formato = useFormato();

  const [modo, setModo] = useState('sesion'); // 'sesion' (sesiones-flask) | 'leccion' (catalogo-flask)

  const [sesion, setSesion] = useState(null);
  const [indice, setIndice] = useState(0);
  const [ultimoResultado, setUltimoResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  // Nivel que se tocó: su botón muestra que está trabajando.
  const [nivelPedido, setNivelPedido] = useState(null);
  const [error, setError] = useState(null);
  const [terminada, setTerminada] = useState(false);
  // RF-IA-01: patrón principal del estudiante, para el aviso de fin de sesión.
  const [patronFinal, setPatronFinal] = useState(null);
  // RF-IA-03: título de cada patrón de la sesión, por código, para los ejercicios adaptados.
  const [titulosPatron, setTitulosPatron] = useState(null);
  // RF-IA-05: desempeño de la sesión terminada (duración, aciertos, ritmo).
  const [desempeno, setDesempeno] = useState(null);

  const [leccion, setLeccion] = useState(null);
  const [indiceLeccion, setIndiceLeccion] = useState(0);

  const ejercicio = sesion?.ejercicios?.[indice];
  const ejercicioLeccion = leccion?.ejercicios?.[indiceLeccion];

  async function empezarLeccion(nivel) {
    setCargando(true);
    setNivelPedido(nivel);
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
    setNivelPedido(nivel);
    setError(null);
    setTerminada(false);
    setUltimoResultado(null);
    setPatronFinal(null);
    setTitulosPatron(null);
    setDesempeno(null);

    try {
      const nueva = await crearSesion({ usuarioId, nivelHsk: nivel });
      setSesion(nueva);
      setIndice(0);
      if (nueva?.ejercicios?.some((e) => e.patron)) cargarTitulosPatron(nueva.id);
      // En segundo plano: la respuesta correcta tras un fallo y "Ver trazos" ya no esperan al catálogo.
      nueva?.ejercicios?.forEach((e) => precargarCaracter(e.caracter));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }

  // Registra la respuesta en sesiones-flask. Lanza si falla: quien llama decide cómo mostrarlo.
  // `codigoError` (RF-IA-01) es el tipo de error de un fallo, si se conoce.
  //
  // Si acertó o no ya se sabe antes de enviar, así que se muestra enseguida
  // (`pendiente`); el próximo repaso y la tasa llegan con la respuesta. Si el
  // envío falla, se deshace: vuelven los botones o el formulario con el error.
  async function registrar(acerto, extra = {}, codigoError) {
    const ejercicioId = ejercicio.id;
    setUltimoResultado({ acerto, ejercicioId, ...extra, pendiente: true });

    let resultado;
    try {
      resultado = await responderEjercicio(ejercicioId, acerto, codigoError);
    } catch (e) {
      setUltimoResultado((r) => (r?.ejercicioId === ejercicioId && r.pendiente ? null : r));
      throw e;
    }
    // Se conserva lo que llegó mientras tanto (la respuesta correcta tras un fallo).
    setUltimoResultado((r) => ({ ...r, ...resultado, acerto, ejercicioId, ...extra, pendiente: false }));

    if (resultado.sesion_completada) {
      setTerminada(true);
      avisarPatron(sesion.id);
      mostrarDesempeno(sesion.id, resultado.desempeno);
    }
  }

  // RF-IA-03: la sesión trae ejercicios dirigidos a un patrón de error. Se
  // busca el título traducido de cada patrón; si falla, queda el texto genérico.
  function cargarTitulosPatron(sesionId) {
    obtenerPatrones(usuarioId)
      .then((r) => {
        const porCodigo = Object.fromEntries((r?.patrones ?? []).map((p) => [p.codigo, p.titulo]));
        setTitulosPatron({ sesionId, porCodigo });
      })
      .catch(() => {});
  }

  // RF-IA-05: la respuesta que cierra la sesión trae el desempeño. Si no
  // vino, se pide aparte; si eso también falla, el cierre queda como estaba.
  function mostrarDesempeno(sesionId, desdeRespuesta) {
    if (desdeRespuesta) {
      setDesempeno(desdeRespuesta);
      return;
    }
    obtenerDesempeno(sesionId)
      .then(setDesempeno)
      .catch(() => {});
  }

  // Al cerrar la sesión se busca el patrón principal para el aviso final. Es
  // un extra: sin patrones, o si la petición falla, el cierre queda como estaba.
  function avisarPatron(sesionId) {
    obtenerPatrones(usuarioId)
      .then((r) => {
        const principal = r?.patrones?.[0];
        if (principal) setPatronFinal({ ...principal, sesionId });
      })
      .catch(() => {});
  }

  // Ejercicios de trazo: el estudiante se califica con "Fallé" o "Acerté".
  async function responder(acerto) {
    setCargando(true);
    setError(null);

    try {
      await registrar(acerto, {}, acerto ? undefined : 'TRAZO_AUTOCALIFICADO');
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }

  // Ejercicios de pinyin (T25): RespuestaPinyin muestra el error y conserva lo escrito si esto falla.
  // El tipo de error es el código de la explicación; "No lo sé" trae el suyo.
  // Sin explicación (el explicador falló) no se manda ninguno.
  async function responderPinyin({ acerto, respuesta, explicacion, nota, codigoError }) {
    const ejercicioId = ejercicio.id;

    // Si falló, se muestra la respuesta correcta (ya suele estar precargada).
    // Si el catálogo no responde, el aviso de acierto o fallo basta.
    if (!acerto) {
      obtenerCaracter(ejercicio.caracter)
        .then((c) =>
          setUltimoResultado((r) => (r?.ejercicioId === ejercicioId ? { ...r, pinyinCorrecto: c.pinyin } : r)),
        )
        .catch(() => {});
    }

    await registrar(acerto, { respuesta, explicacion, nota }, codigoError ?? explicacion?.codigo);
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
        <main className="hm-page practica">
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
              {NIVELES.map((n) =>
                nivelMaximo !== null && n > nivelMaximo ? (
                  // Nivel de Premium: lleva al panel del plan en Progreso. El nombre
                  // accesible sale del texto visible ("HSK 4 Premium", WCAG 2.5.3)
                  // más el destino, solo para lectores de pantalla.
                  <Link
                    key={n}
                    to="/progreso#plan"
                    className="practica-nivel practica-nivel--premium"
                  >
                    <span className="practica-nivel__numeral" lang="zh-Hans" aria-hidden="true">
                      {NUMERALES[n - 1]}
                    </span>
                    <span>HSK {n}</span>
                    <span className="practica-nivel__premium">
                      <IconoCandado /> {t('practice.premiumTag')}
                    </span>
                    <span className="hm-sr">{t('practice.premiumLevel')}</span>
                  </Link>
                ) : (
                  <button
                    key={n}
                    type="button"
                    className="practica-nivel"
                    disabled={cargando}
                    aria-busy={(cargando && nivelPedido === n) || undefined}
                    onClick={() => (modo === 'sesion' ? empezar(n) : empezarLeccion(n))}
                  >
                    <span className="practica-nivel__numeral" lang="zh-Hans" aria-hidden="true">
                      {NUMERALES[n - 1]}
                    </span>
                    <span>HSK {n}</span>
                  </button>
                ),
              )}
            </div>

            {suscripcion && suscripcion.nivel_maximo < NIVELES.length && (
              <p className="practica-nota">
                {t('practice.premiumNote')} <Link to="/progreso#plan">{t('practice.premiumLink')}</Link>
              </p>
            )}
            {sinConfirmar && <p className="practica-nota">{t('practice.planUnknown')}</p>}

            {cargando && (
              <p className="hm-status hm-status--loading" role="status">
                {modo === 'sesion' ? t('practice.buildingSession') : t('practice.buildingLesson')}
              </p>
            )}

            {modo === 'sesion' && <p className="practica-nota">{t('practice.lockedNote')}</p>}
          </section>
        </main>
      </>
    );
  }

  // -------------------------------------------------------------- lección

  if (leccion) {
    if (!ejercicioLeccion) {
      return (
        <>
          <TopBar title={t('practice.lessonDoneBar')} />
          <main className="hm-page practica practica-resumen">
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
          </main>
        </>
      );
    }

    return (
      <>
        <TopBar title={t('practice.lessonBar', { nivel: leccion.nivel_hsk })} />
        <main className="hm-page practica">
          <Avance actual={indiceLeccion} total={leccion.ejercicios.length} />

          <article className="hm-card practica-tarjeta cuadricula-hanzi">
            <span className="hm-kicker">{tipoEjercicio(ejercicioLeccion.tipo)}</span>
            <CuadriculaHanzi hanzi={ejercicioLeccion.caracter.hanzi} />
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
        </main>
      </>
    );
  }

  // ------------------------------------------------------- sesión completa

  if (terminada) {
    const correctas = sesion.ejercicios.length;
    return (
      <>
        <TopBar title={t('practice.sessionDoneBar')} />
        <main className="hm-page practica practica-resumen">
          <span className="hm-seal hm-seal--lg" aria-hidden="true">完</span>
          <h2>{t('practice.sessionDoneTitle')}</h2>
          <p className="practica-intro">
            {t('practice.sessionDoneText', { count: correctas, nivel: sesion.nivel_hsk })}
          </p>

          {ultimoResultado?.aviso && (
            <p className="hm-status hm-status--empty" role="status">{t('practice.progressNotSaved')}</p>
          )}

          {/* RF-IA-05: lo que quedó registrado de esta sesión. */}
          {desempeno?.sesion_id === sesion.id && (
            <section className="hm-card practica-desempeno" aria-labelledby="practica-desempeno-titulo">
              <h3 id="practica-desempeno-titulo" className="hm-kicker">{t('practice.performanceTitle')}</h3>
              <dl>
                <div>
                  <dt>{t('practice.performanceTime')}</dt>
                  <dd>
                    <strong>{formato.duracion(desempeno.duracion_seg)}</strong>
                    <span>
                      {t(desempeno.dentro_del_tiempo ? 'practice.performanceOnTime' : 'practice.performanceOverTime', {
                        minutos: desempeno.duracion_estimada_min,
                      })}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>{t('practice.performanceCorrect')}</dt>
                  <dd>
                    <strong>
                      {t('practice.performanceCorrectValue', { aciertos: desempeno.aciertos, total: desempeno.total })}
                    </strong>
                    <span>{formato.porcentaje(desempeno.tasa_acierto)}</span>
                  </dd>
                </div>
                <div>
                  <dt>{t('practice.performancePace')}</dt>
                  <dd>
                    <strong>
                      {t('practice.performancePaceValue', { tiempo: formato.duracion(desempeno.segundos_por_ejercicio) })}
                    </strong>
                  </dd>
                </div>
              </dl>
            </section>
          )}

          {ultimoResultado && (
            <p className="practica-dato">
              {t('practice.currentAccuracy')}{' '}
              <strong>{tasaAcierto(ultimoResultado.tasa_acierto)}</strong>
            </p>
          )}

          {/* RF-IA-01: una nota, no un error. Solo si hay algún patrón. */}
          {patronFinal?.sesionId === sesion.id && (
            <div className="practica-patron" role="status">
              <p className="hm-kicker practica-patron__etiqueta">{t('practice.patternKicker')}</p>
              <p className="practica-patron__titulo">{patronFinal.titulo}</p>
              <p className="practica-patron__consejo">{patronFinal.consejo}</p>
              <Link to="/progreso" className="practica-patron__enlace">
                {t('practice.seePatterns')}
              </Link>
            </div>
          )}

          <button type="button" className="hm-btn" onClick={() => setSesion(null)}>
            {t('practice.anotherSession')}
          </button>
          <Link to="/progreso" className="practica-enlace">{t('practice.seeProgress')}</Link>
        </main>
      </>
    );
  }

  // -------------------------------------------------------- ejercicio actual

  return (
    <>
      <TopBar
        title={t('practice.sessionBar', { nivel: sesion.nivel_hsk, dificultad: sesion.dificultad })}
      />

      <main className="hm-page practica">
        <Avance actual={indice} total={sesion.ejercicios.length}>
          {ejercicio?.patron ? (
            <span className="practica-refuerzo">{t('practice.adapted')}</span>
          ) : (
            ejercicio?.es_refuerzo && <span className="practica-refuerzo">{t('practice.reinforcement')}</span>
          )}
        </Avance>

        {/* RF-IA-03: el ejercicio apunta a un patrón de error del estudiante. */}
        {ejercicio?.patron && (
          <p className="practica-adaptado">
            {t('practice.adaptedFor')}{' '}
            <strong>
              {(titulosPatron?.sesionId === sesion.id && titulosPatron.porCodigo[ejercicio.patron]) ||
                t('practice.adaptedGeneric')}
            </strong>
          </p>
        )}

        {error && <p className="hm-status hm-status--error" role="alert">{error}</p>}

        <article className="hm-card practica-tarjeta cuadricula-hanzi">
          <span className="hm-kicker">
            {ejercicio?.tipo === 'trazo' ? t('practice.typeStrokes') : t('practice.typePinyin')}
          </span>
          <CuadriculaHanzi hanzi={ejercicio?.caracter} />
        </article>

        {/* Pinyin. Mientras se confirma la respuesta el formulario sigue montado
            (oculto): si el envío falla, vuelve con lo escrito y su error. */}
        {ejercicio?.tipo !== 'trazo' && (!ultimoResultado || ultimoResultado.pendiente) && (
          <div hidden={Boolean(ultimoResultado)}>
            {/* key: un formulario nuevo (vacío) por ejercicio. */}
            <RespuestaPinyin key={ejercicio?.id} caracter={ejercicio?.caracter} onResponder={responderPinyin} />
          </div>
        )}

        {ejercicio?.tipo === 'trazo' && !ultimoResultado && (
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
            <Link to={`/trazos?caracter=${ejercicio.caracter}`} className="practica-enlace">
              {t('practice.seeStrokes')}
            </Link>
          </>
        )}

        {ultimoResultado && (
          <div className="hm-panel practica-feedback" role="status">
            <p className={ultimoResultado.acerto ? 'practica-ok' : 'practica-fallo'}>
              {ultimoResultado.acerto ? t('practice.feedbackCorrect') : t('practice.feedbackFailed')}
            </p>
            {ultimoResultado.acerto && ultimoResultado.nota && (
              <p className="practica-nota">{ultimoResultado.nota.texto}</p>
            )}
            {ultimoResultado.respuesta && (
              <p className="practica-dato">
                {t('practice.yourAnswer')} <strong>{ultimoResultado.respuesta}</strong>
              </p>
            )}
            {ultimoResultado.pinyinCorrecto && (
              <p className="practica-dato">
                {t('practice.correctAnswer')} <strong>{ultimoResultado.pinyinCorrecto}</strong>
              </p>
            )}
            {!ultimoResultado.acerto && ultimoResultado.explicacion && (
              <PorQue explicacion={ultimoResultado.explicacion} />
            )}
            {/* Trazo autocalificado: no hay veredicto del servicio, la pista es fija. */}
            {!ultimoResultado.acerto && ejercicio?.tipo === 'trazo' && (
              <PorQue pista={t('practice.strokeHint')}>
                <Link to={`/trazos?caracter=${ejercicio.caracter}`} className="practica-enlace">
                  {t('practice.seeStrokes')}
                </Link>
              </PorQue>
            )}
            {ultimoResultado.aviso && (
              <p className="hm-status hm-status--empty">{t('practice.progressNotSaved')}</p>
            )}
            {/* El repaso y la tasa los calcula el servidor: hasta que responde, una línea de espera. */}
            <p className="practica-dato">
              {t('practice.nextReview')}{' '}
              {ultimoResultado.pendiente ? (
                <span className="hm-esqueleto practica-esqueleto" />
              ) : (
                <strong>{formato.relativo(ultimoResultado.proximo_repaso) ?? t('practice.notAvailable')}</strong>
              )}
            </p>
            <p className="practica-dato">
              {t('practice.accuracy')}{' '}
              {ultimoResultado.pendiente ? (
                <span className="hm-esqueleto practica-esqueleto" />
              ) : (
                <strong>{tasaAcierto(ultimoResultado.tasa_acierto)}</strong>
              )}
            </p>

            <button
              type="button"
              className="hm-btn hm-btn--block practica-siguiente"
              onClick={siguiente}
              disabled={ultimoResultado.pendiente}
              aria-busy={ultimoResultado.pendiente || undefined}
            >
              {t('practice.next')}
            </button>
          </div>
        )}
      </main>
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
