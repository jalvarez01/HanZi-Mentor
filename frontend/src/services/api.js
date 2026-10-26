/**
 * Cliente HTTP de HanZi Mentor.
 *
 * Todo pasa por el gateway (Nginx), que enruta según el prefijo:
 *   - /api/v2/sesiones/*   -> sesiones-flask: sesiones adaptativas
 *   - /api/v2/ejercicios/* -> sesiones-flask: respuestas
 *   - /api/v2/progreso/*   -> progreso-flask: progreso y repaso
 *   - /api/v2/caracteres/* -> catalogo-flask: caracteres y sus trazos
 *   - /api/v2/lecciones/*  -> catalogo-flask: lecciones
 *   - /api/v2/trazos/*     -> trazos-flask: validación de trazos
 *
 * v2 responde los mismos campos que v1 (contenido y agente-tutor);
 * /api/v1/ sigue en el gateway solo como respaldo. La única diferencia es
 * que responder un ejercicio puede traer `aviso`, con `tasa_acierto` y
 * `proximo_repaso` en null, si el servicio de progreso no respondió.
 *
 * Cada base sale de una variable VITE_* y por defecto es vacía (mismo
 * origen): en desarrollo lo resuelve el proxy de Vite hacia Nginx y en
 * Docker el propio Nginx que sirve el frontend. Solo hace falta definirlas
 * si el gateway está en otro origen (ver frontend/.env.example).
 */

import i18n from '../i18n';

const CATALOGO_URL = import.meta.env.VITE_CATALOGO_URL || '';
const SESIONES_URL = import.meta.env.VITE_SESIONES_URL || '';
const PROGRESO_URL = import.meta.env.VITE_PROGRESO_URL || '';
const TRAZOS_URL = import.meta.env.VITE_TRAZOS_URL || '';

const CATALOGO_API = `${CATALOGO_URL}/api/v2`;
const SESIONES_API = `${SESIONES_URL}/api/v2`;
const PROGRESO_API = `${PROGRESO_URL}/api/v2`;
const TRAZOS_API = `${TRAZOS_URL}/api/v2/trazos`;

class ErrorApi extends Error {
  constructor(mensaje, status, cuerpo) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.status = status;
    this.cuerpo = cuerpo;
    this.codigo = cuerpo?.codigo ?? null;
  }
}

/**
 * Mensaje de error en el idioma activo.
 *
 * Los servicios responden sus errores de negocio en español (p. ej. un nivel
 * no permitido). En español se muestra ese texto tal cual, como antes; en otro
 * idioma se usa un mensaje traducido según el status. El texto del servidor
 * queda siempre disponible en `error.cuerpo`.
 */
function mensajeDeError(status, cuerpo) {
  if (cuerpo?.error && i18n.resolvedLanguage === 'es') return cuerpo.error;
  if (status === 404) return i18n.t('api.notFound');
  if (status === 400 || status === 409) return i18n.t('api.rejected');
  if (status >= 500) return i18n.t('api.server', { status });
  return i18n.t('api.http', { status });
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
    throw new ErrorApi(i18n.t('api.network'), 0, null);
  }

  const texto = await respuesta.text();
  let cuerpo = null;
  try {
    cuerpo = texto ? JSON.parse(texto) : null;
  } catch {
    // Un proxy caído puede responder HTML; se ignora y se usa el status.
  }

  if (!respuesta.ok) {
    throw new ErrorApi(mensajeDeError(respuesta.status, cuerpo), respuesta.status, cuerpo);
  }

  return cuerpo;
}

// ---------------------------------------------------------------- sesiones

export function crearSesion({ usuarioId, nivelHsk, duracionMin = 10 }) {
  return pedir(`${SESIONES_API}/sesiones/`, {
    method: 'POST',
    body: JSON.stringify({
      usuario_id: usuarioId,
      nivel_hsk: nivelHsk,
      duracion_min: duracionMin,
    }),
  });
}

export function obtenerSesion(sesionId) {
  return pedir(`${SESIONES_API}/sesiones/${sesionId}/`);
}

export function responderEjercicio(ejercicioId, acerto) {
  return pedir(`${SESIONES_API}/ejercicios/${ejercicioId}/responder/`, {
    method: 'POST',
    body: JSON.stringify({ acerto }),
  });
}

// ---------------------------------------------------------------- progreso

export function obtenerProgreso(usuarioId) {
  return pedir(`${PROGRESO_API}/progreso/${usuarioId}/`);
}

// --------------------------------------------------------------- contenido

export function listarCaracteres({ nivel, excluir = [], limite = 20 } = {}) {
  const params = new URLSearchParams();
  if (nivel) params.set('nivel', nivel);
  if (excluir.length) params.set('excluir', excluir.join(','));
  params.set('limite', limite);

  return pedir(`${CATALOGO_API}/caracteres/?${params}`);
}

export function obtenerCaracter(hanzi) {
  return pedir(`${CATALOGO_API}/caracteres/${encodeURIComponent(hanzi)}/`);
}

// ------------------------------------------------------------------ trazos

export async function validarTrazo({ mediana, puntos, ancho, alto }) {
  try {
    return await pedir(`${TRAZOS_API}/validar/`, {
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
  return pedir(`${CATALOGO_API}/lecciones/generar/`, {
    method: 'POST',
    body: JSON.stringify({
      usuario_id: usuarioId,
      nivel_hsk: nivelHsk,
      cantidad,
    }),
  });
}

export function obtenerLeccion(leccionId) {
  return pedir(`${CATALOGO_API}/lecciones/${leccionId}/`);
}

export { ErrorApi };
