import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import EjemplosCaracter from '../components/EjemplosCaracter';
import PorQue from '../components/PorQue';
import TopBar from '../components/TopBar';
import { useUsuario } from '../hooks/useUsuario';
import {
  LIMITE_BIBLIOTECA,
  evaluar,
  listarCaracteres,
  obtenerCaracter,
  precargarCaracter,
  registrarErrorDeTrazo,
} from '../services/api';
import './Trazos.css';

// Make Me a Hanzi usa un lienzo de 1024x1024 con el eje Y invertido:
// la esquina superior izquierda está en (0, 900).
const VIEWBOX = 1024;
const TRANSFORM = 'scale(1, -1) translate(0, -900)';

// Errores en los que el trazo no se pudo evaluar: no es un trazo mal hecho.
// DEPENDENCIA_NO_DISPONIBLE viene de evaluacion-flask (catálogo o trazos
// caídos); los otros tres son del gateway (infra/nginx/nginx.conf) cuando el
// propio servicio de evaluación no responde.
const NO_EVALUADO = new Set([
  'DEPENDENCIA_NO_DISPONIBLE',
  'SERVICIO_NO_DISPONIBLE',
  'SERVICIO_SATURADO',
  'TIEMPO_AGOTADO',
]);

export default function Trazos() {
  const [params] = useSearchParams();
  const pedido = params.get('caracter');
  const { t } = useTranslation();
  const { usuarioId } = useUsuario();

  // null mientras llega la lista; [] si llegó vacía o falló.
  const [lista, setLista] = useState(null);
  // El que se tocó en la biblioteca; se marca enseguida, antes de que llegue su detalle.
  const [elegido, setElegido] = useState(null);
  const [caracter, setCaracter] = useState(null);
  const [fallido, setFallido] = useState(null);
  const [trazoActual, setTrazoActual] = useState(0);
  const [error, setError] = useState(null);
  // Hanzi del carácter que está a la vista (para no volver a pedirlo).
  const mostrado = caracter?.hanzi ?? null;

  // Carga la lista de caracteres disponibles.
  useEffect(() => {
    listarCaracteres({ limite: LIMITE_BIBLIOTECA })
      .then((r) => setLista(r.caracteres || []))
      .catch((e) => {
        setLista([]);
        setError(e.message);
      });
  }, []);

  // El carácter a mostrar: el elegido, el que vino en la URL o el primero de la lista.
  const objetivo = elegido || pedido || lista?.[0]?.hanzi || null;

  // Carga el detalle (con trazos) del carácter. Con ?caracter= no espera a la
  // lista: las dos peticiones salen a la vez.
  useEffect(() => {
    if (!objetivo || mostrado === objetivo) return undefined;
    let vigente = true;
    obtenerCaracter(objetivo)
      .then((c) => {
        if (!vigente) return;
        setCaracter(c);
        setTrazoActual(0);
      })
      .catch((e) => {
        if (!vigente) return;
        setError(e.message);
        setFallido(objetivo);
        // La biblioteca vuelve a marcar el carácter que sigue a la vista.
        setElegido(mostrado);
      });
    return () => {
      vigente = false;
    };
  }, [objetivo, mostrado]);

  function elegir(hanzi) {
    setError(null);
    setFallido(null);
    setElegido(hanzi);
  }

  const cargandoCaracter = Boolean(objetivo) && objetivo !== mostrado && objetivo !== fallido;
  // Los ejemplos se piden con el carácter elegido, sin esperar su detalle.
  const hanziVista = objetivo && objetivo !== fallido ? objetivo : caracter?.hanzi;

  const trazos = caracter?.trazos || [];
  const sinTrazos = caracter && !cargandoCaracter && trazos.length === 0;

  return (
    <>
      <TopBar title={t('strokes.title')} />

      <main className="hm-page trazos">
        {error && <p className="hm-status hm-status--error" role="alert">{error}</p>}

        {/* Mientras llega el primero, la ficha guarda su lugar con el mismo tamaño. */}
        {(caracter || cargandoCaracter) && (
          <div className="hm-card trazos-ficha" aria-busy={cargandoCaracter || undefined}>
            <span className="trazos-ficha__hanzi" lang="zh-Hans">
              {caracter ? caracter.hanzi : <span className="hm-esqueleto trazos-esqueleto trazos-esqueleto--hanzi" />}
            </span>
            <div>
              <span className="hm-kicker">{t('strokes.cardKicker')}</span>
              <p className="trazos-ficha__pinyin">
                {caracter ? caracter.pinyin || '—' : <span className="hm-esqueleto trazos-esqueleto" style={{ width: '4em' }} />}
              </p>
              <p className="trazos-ficha__def">
                {caracter
                  ? caracter.definicion || t('strokes.noDefinition')
                  : <span className="hm-esqueleto trazos-esqueleto" style={{ width: '12em' }} />}
              </p>
            </div>
            {cargandoCaracter && <span className="hm-sr" role="status">{t('strokes.loading')}</span>}
          </div>
        )}

        {sinTrazos ? (
          <p className="hm-status hm-status--empty">{t('strokes.noStrokeData')}</p>
        ) : (
          <>
            <LienzoTrazos
              trazos={trazos}
              hasta={trazoActual}
              hanzi={caracter?.hanzi}
              usuarioId={usuarioId}
              onAprobado={() => setTrazoActual((n) => Math.min(trazos.length, n + 1))}
              key={caracter?.hanzi}
            />

            {/* Sin trazos todavía, los controles ocupan su lugar sin verse. */}
            {(trazos.length > 0 || cargandoCaracter) && (
              <div
                className={`trazos-controles ${trazos.length ? '' : 'trazos-controles--espera'}`}
                aria-hidden={trazos.length ? undefined : true}
              >
                <button
                  type="button"
                  className="trazos-control"
                  onClick={() => setTrazoActual((n) => Math.max(0, n - 1))}
                  disabled={trazoActual === 0}
                >
                  {t('strokes.previous')}
                </button>
                <span className="trazos-paso" aria-live="polite">
                  {t('strokes.step', { actual: trazoActual, total: trazos.length })}
                </span>
                <button
                  type="button"
                  className="trazos-control"
                  onClick={() => setTrazoActual((n) => Math.min(trazos.length, n + 1))}
                  disabled={trazoActual === trazos.length}
                >
                  {t('strokes.next')}
                </button>
              </div>
            )}
          </>
        )}

        {hanziVista && <EjemplosCaracter hanzi={hanziVista} />}

        <section className="hm-panel trazos-lista" aria-labelledby="trazos-lista-titulo">
          <div className="hm-section-head">
            <div>
              <span className="hm-kicker">{t('strokes.listKicker')}</span>
              <h2 id="trazos-lista-titulo">{t('strokes.listTitle')}</h2>
            </div>
          </div>

          <div className="trazos-grilla" aria-busy={lista === null || undefined}>
            {lista === null
              ? Array.from({ length: LIMITE_BIBLIOTECA }, (_, i) => (
                  <span key={i} className="trazos-celda trazos-celda--esqueleto hm-esqueleto" aria-hidden="true" />
                ))
              : lista.map((c) => (
                  <button
                    key={c.hanzi}
                    type="button"
                    lang="zh-Hans"
                    className={`trazos-celda ${objetivo === c.hanzi ? 'is-activa' : ''}`}
                    aria-pressed={objetivo === c.hanzi}
                    aria-busy={(cargandoCaracter && objetivo === c.hanzi) || undefined}
                    // Al pasar el puntero o enfocar ya se pide: al tocar suele estar listo.
                    onPointerEnter={() => precargarCaracter(c.hanzi)}
                    onFocus={() => precargarCaracter(c.hanzi)}
                    onClick={() => elegir(c.hanzi)}
                  >
                    {c.hanzi}
                  </button>
                ))}
          </div>

          {lista?.length === 0 && <p className="hm-status hm-status--empty">{t('strokes.listEmpty')}</p>}
        </section>
      </main>
    </>
  );
}

/**
 * Muestra los trazos hasta el índice indicado y deja dibujar encima.
 *
 * El SVG de fondo pinta el trazo correcto; el canvas de arriba captura el
 * dedo o el mouse. Al soltar, el trazo capturado se manda a evaluar
 * (RF-APR-01) y, si se aprueba, se avanza solo al trazo siguiente. Si el
 * aprobado trae una nota de mejora (RF-IA-04), no se avanza solo: la nota
 * queda a la vista y se sigue con "Siguiente".
 *
 * RF-IA-01: un trazo fallado que el servicio pudo explicar anota su tipo de
 * error en el progreso, sin esperar la respuesta. Solo alimenta los patrones
 * de error; si falla, acá no cambia nada.
 */
function LienzoTrazos({ trazos, hasta, hanzi, usuarioId, onAprobado }) {
  const { t } = useTranslation();
  const canvasRef = useRef(null);
  const dibujando = useRef(false);
  const puntosRef = useRef([]);
  // Posición del lienzo, medida al empezar cada trazo: medirla en cada
  // movimiento obliga al navegador a recalcular el layout mientras se dibuja.
  const rectRef = useRef(null);
  const [tieneDibujo, setTieneDibujo] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [validando, setValidando] = useState(false);
  // No se pudo evaluar (servicio caído o sin red): no es un trazo mal hecho.
  const [sinEvaluar, setSinEvaluar] = useState(false);

  const trazoActual = trazos[hasta];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Ajusta la resolución interna al tamaño real en pantalla,
    // así el trazo no se ve pixelado en pantallas densas.
    const rect = canvas.getBoundingClientRect();
    const escala = window.devicePixelRatio || 1;

    canvas.width = rect.width * escala;
    canvas.height = rect.height * escala;

    const ctx = canvas.getContext('2d');
    ctx.scale(escala, escala);
    ctx.lineWidth = 8;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    // El color sale de --trazo-usuario (vía `color` en .lienzo-canvas), no del JS.
    ctx.strokeStyle = getComputedStyle(canvas).color;

    // Nuevo trazo: se limpia el lienzo anterior y su veredicto.
    puntosRef.current = [];
    setTieneDibujo(false);
    setResultado(null);
    setSinEvaluar(false);
  }, [hasta]);

  function posicion(evento) {
    const rect = rectRef.current ?? canvasRef.current.getBoundingClientRect();
    const punto = evento.touches?.[0] || evento;
    return {
      x: punto.clientX - rect.left,
      y: punto.clientY - rect.top,
    };
  }

  function empezar(evento) {
    evento.preventDefault();
    rectRef.current = canvasRef.current.getBoundingClientRect();
    dibujando.current = true;
    setTieneDibujo(true);
    setResultado(null);
    setSinEvaluar(false);

    const { x, y } = posicion(evento);
    puntosRef.current = [{ x, y }];

    const ctx = canvasRef.current.getContext('2d');
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function mover(evento) {
    if (!dibujando.current) return;
    evento.preventDefault();

    const { x, y } = posicion(evento);
    puntosRef.current.push({ x, y });

    const ctx = canvasRef.current.getContext('2d');
    ctx.lineTo(x, y);
    ctx.stroke();
  }

  async function terminar() {
    if (!dibujando.current) return;
    dibujando.current = false;

    const puntos = puntosRef.current;
    if (puntos.length < 2 || !trazoActual || !hanzi) return;

    const rect = rectRef.current ?? canvasRef.current.getBoundingClientRect();

    setValidando(true);
    try {
      // evaluacion-flask busca la mediana en el catálogo y compara con trazos-flask.
      const veredicto = await evaluar({
        tipo: 'trazo',
        caracter: hanzi,
        respuesta: {
          secuencia: trazoActual.secuencia,
          puntos,
          ancho: Math.round(rect.width),
          alto: Math.round(rect.height),
        },
      });
      setResultado(veredicto);

      if (!veredicto.aprobado && veredicto.explicacion?.codigo && usuarioId) {
        registrarErrorDeTrazo(usuarioId, {
          caracter: hanzi,
          codigoError: veredicto.explicacion.codigo,
        }).catch(() => {});
      }

      if (veredicto.aprobado && !veredicto.nota) {
        setTimeout(() => onAprobado?.(), 900);
      }
    } catch (e) {
      // Sin status: no llegó respuesta (sin red o servidor inalcanzable).
      if (NO_EVALUADO.has(e.codigo) || !e.status) {
        setSinEvaluar(true);
      } else {
        setResultado({ aprobado: false, invertido: false, detalle: e.message });
      }
    } finally {
      setValidando(false);
    }
  }

  function limpiar() {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    puntosRef.current = [];
    setTieneDibujo(false);
    setResultado(null);
    setSinEvaluar(false);
  }

  return (
    <>
      <div className="lienzo-wrap">
        <svg className="lienzo-svg" viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`} aria-hidden="true">
          <line x1="512" y1="0" x2="512" y2="1024" className="guia" />
          <line x1="0" y1="512" x2="1024" y2="512" className="guia" />

          <g transform={TRANSFORM}>
            {trazos.map((trazo, i) => (
              <path
                key={trazo.secuencia}
                d={trazo.path_svg}
                className={i < hasta ? 'trazo-hecho' : 'trazo-pendiente'}
              />
            ))}
          </g>
        </svg>

        <canvas
          ref={canvasRef}
          className="lienzo-canvas"
          aria-label={t('strokes.canvasLabel')}
          onMouseDown={empezar}
          onMouseMove={mover}
          onMouseUp={terminar}
          onMouseLeave={terminar}
          onTouchStart={empezar}
          onTouchMove={mover}
          onTouchEnd={terminar}
        />

        {tieneDibujo && (
          <button type="button" className="limpiar" onClick={limpiar}>
            {t('strokes.clear')}
          </button>
        )}

        {/* Sobre el lienzo, apenas se suelta: no empuja lo de abajo mientras llega el veredicto. */}
        {validando && <p className="validando" role="status">{t('strokes.checking')}</p>}
      </div>

      {sinEvaluar && (
        <p className="hm-status hm-status--empty" role="status">{t('strokes.unavailable')}</p>
      )}

      {resultado && (
        <div
          role="status"
          className={`resultado ${
            resultado.aprobado ? 'aprobado' : resultado.invertido ? 'invertido' : 'fallado'
          }`}
        >
          {typeof resultado.puntaje === 'number' && (
            <span className="resultado-puntaje">{resultado.puntaje}</span>
          )}
          <p className="resultado-detalle">{resultado.detalle}</p>
          {resultado.invertido && <span className="resultado-tag">{t('strokes.reversed')}</span>}
        </div>
      )}

      {/* RF-IA-04: un aprobado "aceptable" dice dónde mejorar. */}
      {resultado?.aprobado && resultado.nota && (
        <p className="trazos-nota" role="status">
          {resultado.nota.texto} <span className="trazos-nota__seguir">{t('strokes.noteNext')}</span>
        </p>
      )}

      {/* RF-IA-04: solo con un trazo fallado que el servicio pudo explicar. */}
      {resultado && !resultado.aprobado && resultado.explicacion && (
        <PorQue explicacion={resultado.explicacion} anunciar />
      )}
    </>
  );
}
