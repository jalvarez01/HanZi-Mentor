import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import TopBar from '../components/TopBar';
import { listarCaracteres, obtenerCaracter } from '../services/api';
import './Trazos.css';

// Make Me a Hanzi usa un lienzo de 1024x1024 con el eje Y invertido:
// la esquina superior izquierda está en (0, 900).
const VIEWBOX = 1024;
const TRANSFORM = 'scale(1, -1) translate(0, -900)';

export default function Trazos() {
  const [params] = useSearchParams();
  const pedido = params.get('caracter');

  const [lista, setLista] = useState([]);
  const [caracter, setCaracter] = useState(null);
  const [trazoActual, setTrazoActual] = useState(0);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);

  // Carga la lista de caracteres disponibles.
  useEffect(() => {
    listarCaracteres({ limite: 30 })
      .then((r) => setLista(r.caracteres || []))
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, []);

  // Carga el detalle (con trazos) del carácter elegido.
  useEffect(() => {
    const objetivo = pedido || lista[0]?.hanzi;
    if (!objetivo) return;

    setCargando(true);
    obtenerCaracter(objetivo)
      .then((c) => {
        setCaracter(c);
        setTrazoActual(0);
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [pedido, lista]);

  function elegir(hanzi) {
    setCargando(true);
    setError(null);
    obtenerCaracter(hanzi)
      .then((c) => {
        setCaracter(c);
        setTrazoActual(0);
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }

  const trazos = caracter?.trazos || [];
  const sinTrazos = caracter && trazos.length === 0;

  return (
    <>
      <TopBar title="Trazos" />

      <div className="screen-pad trazos">
        {error && <p className="error">{error}</p>}

        {caracter && (
          <div className="ficha">
            <span className="ficha-hanzi">{caracter.hanzi}</span>
            <div>
              <p className="ficha-pinyin">{caracter.pinyin || '—'}</p>
              <p className="ficha-def">{caracter.definicion || 'sin definición'}</p>
            </div>
          </div>
        )}

        {sinTrazos ? (
          <p className="aviso">
            Este carácter todavía no tiene datos de trazos cargados. Corré
            <code> cargar_hanzi </code> en el servicio de contenido.
          </p>
        ) : (
          <>
            <LienzoTrazos
              trazos={trazos}
              hasta={trazoActual}
              key={caracter?.hanzi}
            />

            {trazos.length > 0 && (
              <div className="controles">
                <button
                  onClick={() => setTrazoActual((n) => Math.max(0, n - 1))}
                  disabled={trazoActual === 0}
                >
                  Anterior
                </button>
                <span className="paso">
                  trazo {trazoActual} de {trazos.length}
                </span>
                <button
                  onClick={() => setTrazoActual((n) => Math.min(trazos.length, n + 1))}
                  disabled={trazoActual === trazos.length}
                >
                  Siguiente
                </button>
              </div>
            )}
          </>
        )}

        {cargando && <p className="cargando">Cargando…</p>}

        <h3 className="titulo-lista">Elegí un carácter</h3>
        <div className="grilla">
          {lista.map((c) => (
            <button
              key={c.hanzi}
              className={`celda ${caracter?.hanzi === c.hanzi ? 'activa' : ''}`}
              onClick={() => elegir(c.hanzi)}
            >
              {c.hanzi}
            </button>
          ))}
        </div>

        {!cargando && lista.length === 0 && (
          <p className="aviso">
            No hay caracteres cargados. Levantá el servicio de contenido en el
            puerto 8002 y cargá datos.
          </p>
        )}
      </div>
    </>
  );
}

/**
 * Muestra los trazos hasta el índice indicado y deja dibujar encima.
 *
 * El SVG de fondo pinta el trazo correcto; el canvas de arriba captura el
 * dedo o el mouse. Todavía no compara ambos: eso es RF-APR-01.
 */
function LienzoTrazos({ trazos, hasta }) {
  const canvasRef = useRef(null);
  const dibujando = useRef(false);
  const [tieneDibujo, setTieneDibujo] = useState(false);

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
    ctx.strokeStyle = '#B23A2E';
  }, [hasta]);

  function posicion(evento) {
    const rect = canvasRef.current.getBoundingClientRect();
    const punto = evento.touches?.[0] || evento;
    return {
      x: punto.clientX - rect.left,
      y: punto.clientY - rect.top,
    };
  }

  function empezar(evento) {
    evento.preventDefault();
    dibujando.current = true;
    setTieneDibujo(true);

    const ctx = canvasRef.current.getContext('2d');
    const { x, y } = posicion(evento);
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function mover(evento) {
    if (!dibujando.current) return;
    evento.preventDefault();

    const ctx = canvasRef.current.getContext('2d');
    const { x, y } = posicion(evento);
    ctx.lineTo(x, y);
    ctx.stroke();
  }

  function terminar() {
    dibujando.current = false;
  }

  function limpiar() {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setTieneDibujo(false);
  }

  return (
    <div className="lienzo-wrap">
      <svg className="lienzo-svg" viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}>
        <line x1="512" y1="0" x2="512" y2="1024" className="guia" />
        <line x1="0" y1="512" x2="1024" y2="512" className="guia" />

        <g transform={TRANSFORM}>
          {trazos.map((t, i) => (
            <path
              key={t.secuencia}
              d={t.path_svg}
              className={i < hasta ? 'trazo-hecho' : 'trazo-pendiente'}
            />
          ))}
        </g>
      </svg>

      <canvas
        ref={canvasRef}
        className="lienzo-canvas"
        onMouseDown={empezar}
        onMouseMove={mover}
        onMouseUp={terminar}
        onMouseLeave={terminar}
        onTouchStart={empezar}
        onTouchMove={mover}
        onTouchEnd={terminar}
      />

      {tieneDibujo && (
        <button className="limpiar" onClick={limpiar}>
          Borrar
        </button>
      )}
    </div>
  );
}
