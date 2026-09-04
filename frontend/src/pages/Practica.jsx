import { useState } from 'react';
import { Link } from 'react-router-dom';
import TopBar from '../components/TopBar';
import { useUsuario } from '../hooks/useUsuario';
import { crearSesion, responderEjercicio, generarLeccion } from '../services/api';
import './Practica.css';

const NIVELES = [1, 2, 3, 4, 5, 6];

export default function Practica() {
  const { usuarioId } = useUsuario();

  const [modo, setModo] = useState('sesion'); // 'sesion' (agente-tutor) | 'leccion' (contenido)

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

  // ---------------------------------------------------------- sin sesión

  if (!sesion && !leccion) {
    return (
      <>
        <TopBar title="Practicar" />
        <div className="screen-pad practica">
          <div className="niveles" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 20 }}>
            <button
              className="nivel-btn"
              style={modo === 'sesion' ? { background: 'var(--gold)', color: 'var(--paper)' } : undefined}
              onClick={() => setModo('sesion')}
            >
              Sesión adaptativa
            </button>
            <button
              className="nivel-btn"
              style={modo === 'leccion' ? { background: 'var(--gold)', color: 'var(--paper)' } : undefined}
              onClick={() => setModo('leccion')}
            >
              Lección por nivel
            </button>
          </div>

          <p className="intro">
            {modo === 'sesion'
              ? 'Elegí un nivel. El tutor arma la sesión priorizando lo que venís fallando.'
              : 'Elegí un nivel. Se genera una lección con caracteres y ejercicios de ese HSK.'}
          </p>

          {error && <p className="error">{error}</p>}

          <div className="niveles">
            {NIVELES.map((n) => (
              <button
                key={n}
                className="nivel-btn"
                disabled={cargando}
                onClick={() => (modo === 'sesion' ? empezar(n) : empezarLeccion(n))}
              >
                HSK{n}
              </button>
            ))}
          </div>

          {cargando && <p className="cargando">Armando tu {modo === 'sesion' ? 'sesión' : 'lección'}…</p>}

          {modo === 'sesion' && (
            <p className="nota">
              Si un nivel no está desbloqueado, el servidor lo rechaza — es la regla
              que valida el builder.
            </p>
          )}
        </div>
      </>
    );
  }

   // -------------------------------------------------------------- lección

  if (leccion) {
    if (!ejercicioLeccion) {
      return (
        <>
          <TopBar title="Lección completa" />
          <div className="screen-pad practica resumen">
            <div className="sello-grande">完</div>
            <h2>Terminaste la lección</h2>
            <p className="intro">
              Revisaste los {leccion.ejercicios.length} ejercicios de nivel HSK{leccion.nivel_hsk}.
            </p>
            <button className="btn-principal" onClick={() => { setLeccion(null); setIndiceLeccion(0); }}>
              Otra lección
            </button>
          </div>
        </>
      );
    }

    return (
      <>
        <TopBar title={`HSK${leccion.nivel_hsk} · Lección`} />
        <div className="screen-pad practica">
          <div className="barra-avance">
            <div
              className="barra-relleno"
              style={{ width: `${(indiceLeccion / leccion.ejercicios.length) * 100}%` }}
            />
          </div>
          <p className="contador">
            {indiceLeccion + 1} de {leccion.ejercicios.length}
          </p>

          <div className="tarjeta-ejercicio">
            <div className="hanzi-grande">{ejercicioLeccion.caracter.hanzi}</div>
            <p className="tipo">
              {ejercicioLeccion.tipo === 'trazo' ? 'Orden de trazos' : 'Significado'}
            </p>
            <p className="dato">{ejercicioLeccion.caracter.pinyin} · {ejercicioLeccion.caracter.definicion}</p>
          </div>

          {ejercicioLeccion.tipo === 'trazo' && (
            <Link to={`/trazos?caracter=${ejercicioLeccion.caracter.hanzi}`} className="btn-texto">
              Ver el orden de trazos
            </Link>
          )}

          <button className="btn-principal" onClick={() => setIndiceLeccion((i) => i + 1)}>
            Siguiente
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
        <TopBar title="Sesión completa" />
        <div className="screen-pad practica resumen">
          <div className="sello-grande">完</div>
          <h2>Terminaste la sesión</h2>
          <p className="intro">
            Respondiste los {correctas} ejercicios de nivel HSK{sesion.nivel_hsk}.
          </p>

          {ultimoResultado && (
            <p className="dato">
              Tasa de acierto actual: <strong>{Math.round(ultimoResultado.tasa_acierto * 100)}%</strong>
            </p>
          )}

          <button className="btn-principal" onClick={() => setSesion(null)}>
            Otra sesión
          </button>
          <Link to="/progreso" className="btn-texto">Ver mi progreso</Link>
        </div>
      </>
    );
  }

  // -------------------------------------------------------- ejercicio actual

  return (
    <>
      <TopBar title={`HSK${sesion.nivel_hsk} · dificultad ${sesion.dificultad}`} />

      <div className="screen-pad practica">
        <div className="barra-avance">
          <div
            className="barra-relleno"
            style={{ width: `${(indice / sesion.ejercicios.length) * 100}%` }}
          />
        </div>
        <p className="contador">
          {indice + 1} de {sesion.ejercicios.length}
          {ejercicio?.es_refuerzo && <span className="etiqueta-refuerzo">refuerzo</span>}
        </p>

        {error && <p className="error">{error}</p>}

        <div className="tarjeta-ejercicio">
          <div className="hanzi-grande">{ejercicio?.caracter}</div>
          <p className="tipo">
            {ejercicio?.tipo === 'trazo' ? 'Orden de trazos' : 'Significado'}
          </p>
        </div>

        {!ultimoResultado ? (
          <>
            <p className="pregunta">¿Lo respondiste bien?</p>
            <div className="acciones">
              <button
                className="btn-mal"
                disabled={cargando}
                onClick={() => responder(false)}
              >
                Fallé
              </button>
              <button
                className="btn-bien"
                disabled={cargando}
                onClick={() => responder(true)}
              >
                Acerté
              </button>
            </div>
            {ejercicio?.tipo === 'trazo' && (
              <Link to={`/trazos?caracter=${ejercicio.caracter}`} className="btn-texto">
                Ver el orden de trazos
              </Link>
            )}
          </>
        ) : (
          <div className="feedback">
            <p className={ultimoResultado.acerto ? 'ok' : 'fallo'}>
              {ultimoResultado.acerto ? 'Sumado a tu racha' : 'Vuelve pronto al repaso'}
            </p>
            <p className="dato">
              Próximo repaso:{' '}
              <strong>{formatearFecha(ultimoResultado.proximo_repaso)}</strong>
            </p>
            <p className="dato">
              Tasa de acierto: <strong>{Math.round(ultimoResultado.tasa_acierto * 100)}%</strong>
            </p>

            <button className="btn-principal" onClick={siguiente}>
              Siguiente
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function formatearFecha(iso) {
  if (!iso) return '—';

  const fecha = new Date(iso);
  const horas = Math.round((fecha - new Date()) / 36e5);

  if (horas < 24) return `en ${horas} h`;
  return `en ${Math.round(horas / 24)} días`;
}
