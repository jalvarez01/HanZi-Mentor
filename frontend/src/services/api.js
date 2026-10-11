/**
 * Cliente HTTP de HanZi Mentor.
 *
 * Habla con dos servicios distintos:
 *   - agente-tutor (8003): sesiones, respuestas, progreso
 *   - contenido    (8002): caracteres y sus trazos
 *   - trazos-flask (v2, vía Nginx): validación de trazos
 *
 * Las URLs salen de variables de entorno de Vite para no hardcodear puertos.
 * Creá un archivo `.env.local` en frontend/ si necesitás cambiarlas.
 */

const TUTOR_URL = import.meta.env.VITE_TUTOR_URL || 'http://localhost:8003';
const CONTENIDO_URL = import.meta.env.VITE_CONTENIDO_URL || 'http://localhost:8002';
// Vacío = mismo origen: en desarrollo lo resuelve el proxy de Vite hacia Nginx.
const TRAZOS_URL = import.meta.env.VITE_TRAZOS_URL || '';

class ErrorApi extends Error {
  constructor(mensaje, status, cuerpo) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.status = status;
    this.cuerpo = cuerpo;
    this.codigo = cuerpo?.codigo ?? null;
  }
}

async function pedir(url, opciones = {}) {
  let respuesta;

  try {
    respuesta = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...opciones,
    });
  } catch {
    // fetch solo tira excepción si la red falla; un 400 llega como respuesta.
    throw new ErrorApi(
      'No se pudo conectar con el servidor. ¿Está corriendo el backend?',
      0,
      null,
    );
  }

  const texto = await respuesta.text();
  let cuerpo = null;
  try {
    cuerpo = texto ? JSON.parse(texto) : null;
  } catch {
    // Un proxy caído puede responder HTML; se ignora y se usa el status.
  }

  if (!respuesta.ok) {
    throw new ErrorApi(
      cuerpo?.error || `Error ${respuesta.status}`,
      respuesta.status,
      cuerpo,
    );
  }

  return cuerpo;
}

// ---------------------------------------------------------------- sesiones

export function crearSesion({ usuarioId, nivelHsk, duracionMin = 10 }) {
  return pedir(`${TUTOR_URL}/api/sesiones/`, {
    method: 'POST',
    body: JSON.stringify({
      usuario_id: usuarioId,
      nivel_hsk: nivelHsk,
      duracion_min: duracionMin,
    }),
  });
}

export function obtenerSesion(sesionId) {
  return pedir(`${TUTOR_URL}/api/sesiones/${sesionId}/`);
}

export function responderEjercicio(ejercicioId, acerto) {
  return pedir(`${TUTOR_URL}/api/ejercicios/${ejercicioId}/responder/`, {
    method: 'POST',
    body: JSON.stringify({ acerto }),
  });
}

// ---------------------------------------------------------------- progreso

export function obtenerProgreso(usuarioId) {
  return pedir(`${TUTOR_URL}/api/progreso/${usuarioId}/`);
}

// --------------------------------------------------------------- contenido

export function listarCaracteres({ nivel, excluir = [], limite = 20 } = {}) {
  const params = new URLSearchParams();
  if (nivel) params.set('nivel', nivel);
  if (excluir.length) params.set('excluir', excluir.join(','));
  params.set('limite', limite);

  return pedir(`${CONTENIDO_URL}/api/caracteres/?${params}`);
}

export function obtenerCaracter(hanzi) {
  return pedir(`${CONTENIDO_URL}/api/caracteres/${encodeURIComponent(hanzi)}/`);
}

// ------------------------------------------------------------------ trazos

export async function validarTrazo({ mediana, puntos, ancho, alto }) {
  try {
    return await pedir(`${TRAZOS_URL}/api/v2/trazos/validar/`, {
      method: 'POST',
      body: JSON.stringify({ mediana, puntos, ancho, alto }),
    });
  } catch (e) {
    // 400 ENTRADA_INVALIDA / 500 ERROR_INTERNO: se muestra el código junto al mensaje.
    if (e instanceof ErrorApi && e.codigo) {
      throw new ErrorApi(`${e.message} (${e.codigo})`, e.status, e.cuerpo);
    }
    throw e;
  }
}

// ---------------------------------------------------------------- lecciones
 
export function generarLeccion({ usuarioId, nivelHsk, cantidad = 10 }) {
  return pedir(`${CONTENIDO_URL}/api/lecciones/generar/`, {
    method: 'POST',
    body: JSON.stringify({
      usuario_id: usuarioId,
      nivel_hsk: nivelHsk,
      cantidad,
    }),
  });
}
 
export function obtenerLeccion(leccionId) {
  return pedir(`${CONTENIDO_URL}/api/lecciones/${leccionId}/`);
}
 
export { ErrorApi };
