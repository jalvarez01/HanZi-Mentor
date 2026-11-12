/**
 * Cliente HTTP de HanZi Mentor.
 *
 * Todo pasa por el gateway (Nginx), que enruta según el prefijo:
 *   - /api/v2/sesiones/*   -> sesiones-flask: sesiones adaptativas
 *   - /api/v2/ejercicios/* -> sesiones-flask: respuestas
 *   - /api/v2/progreso/*   -> progreso-flask: progreso y repaso
 *   - /api/v2/caracteres/* -> catalogo-flask: caracteres y sus trazos
 *   - /api/v2/lecciones/*  -> catalogo-flask: lecciones
 *   - /api/v2/evaluacion/* -> evaluacion-flask: decide si una respuesta es
 *                             correcta (el trazo lo compara trazos-flask, que
 *                             queda como servicio interno)
 *   - /api/v2/ejemplos/*   -> ejemplos-flask: oraciones de ejemplo de Tatoeba
 *                             (API de terceros detrás de un Adapter)
 *   - /api/v2/reportes/*   -> reportes-flask: reportes de progreso que genera
 *                             en segundo plano un worker de Celery
 *   - /api/v2/suscripciones/* -> suscripciones-flask: planes Free y Premium
 *                             con pago simulado (RF-USR-01)
 *
 * v2 responde los mismos campos que v1 (contenido y agente-tutor);
 * /api/v1/ sigue en el gateway solo como respaldo. La única diferencia es
 * que responder un ejercicio puede traer `aviso`, con `tasa_acierto` y
 * `proximo_repaso` en null, si el servicio de progreso no respondió.
 *
 * RF-IA-01: al responder un fallo se manda su tipo en `codigo_error`, la
 * página Trazos anota los suyos en progreso/<id>/errores/ y los patrones que
 * salen de ahí se leen en progreso/<id>/patrones/.
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
const EVALUACION_URL = import.meta.env.VITE_EVALUACION_URL || '';
const EJEMPLOS_URL = import.meta.env.VITE_EJEMPLOS_URL || '';
const REPORTES_URL = import.meta.env.VITE_REPORTES_URL || '';
const SUSCRIPCIONES_URL = import.meta.env.VITE_SUSCRIPCIONES_URL || '';

const CATALOGO_API = `${CATALOGO_URL}/api/v2`;
const SESIONES_API = `${SESIONES_URL}/api/v2`;
const PROGRESO_API = `${PROGRESO_URL}/api/v2`;
const EVALUACION_API = `${EVALUACION_URL}/api/v2`;
const EJEMPLOS_API = `${EJEMPLOS_URL}/api/v2`;
const REPORTES_API = `${REPORTES_URL}/api/v2`;
const SUSCRIPCIONES_API = `${SUSCRIPCIONES_URL}/api/v2/suscripciones`;

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
 * Cada petición manda el idioma del selector en Accept-Language y los
 * servicios responden `error` ya traducido (es o en), así que se muestra tal
 * cual. Si la respuesta no trae `error` (un proxy caído, por ejemplo), se usa
 * un mensaje propio según el status. El cuerpo queda en `error.cuerpo`.
 */
function mensajeDeError(status, cuerpo) {
  if (cuerpo?.error) return cuerpo.error;
  if (status === 404) return i18n.t('api.notFound');
  if (status === 400 || status === 409) return i18n.t('api.rejected');
  if (status >= 500) return i18n.t('api.server', { status });
  return i18n.t('api.http', { status });
}

async function pedir(url, opciones = {}) {
  let respuesta;

  try {
    respuesta = await fetch(url, {
      // El backend elige el idioma de sus mensajes con esta cabecera.
      headers: { 'Content-Type': 'application/json', 'Accept-Language': i18n.resolvedLanguage },
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

/**
 * `codigoError` (RF-IA-01) es el tipo de error de una respuesta fallada: el
 * `explicacion.codigo` de la evaluación, NO_SABE o TRAZO_AUTOCALIFICADO. Es
 * opcional y solo se manda con un fallo.
 */
export function responderEjercicio(ejercicioId, acerto, codigoError) {
  const cuerpo = { acerto };
  if (!acerto && codigoError) cuerpo.codigo_error = codigoError;

  return pedir(`${SESIONES_API}/ejercicios/${ejercicioId}/responder/`, {
    method: 'POST',
    body: JSON.stringify(cuerpo),
  });
}

/**
 * Desempeño de una sesión terminada (RF-IA-05): duración, fecha y
 * resultados. La respuesta que cierra la sesión ya lo trae en `desempeno`;
 * esto sirve para pedirlo después. 409 si la sesión sigue en curso.
 */
export function obtenerDesempeno(sesionId) {
  return pedir(`${SESIONES_API}/sesiones/${sesionId}/desempeno/`);
}

// ---------------------------------------------------------------- progreso

export function obtenerProgreso(usuarioId) {
  return pedir(`${PROGRESO_API}/progreso/${usuarioId}/`);
}

/**
 * Patrones de error del estudiante (RF-IA-01), del más relevante al menos
 * relevante: { usuario_id, ventana_dias, patrones: [{ codigo, tipo,
 * frecuencia, caracteres, ultima_vez, titulo, consejo }] }. `titulo` y
 * `consejo` llegan en el idioma activo. Sin datos suficientes, `patrones` es [].
 */
export function obtenerPatrones(usuarioId) {
  return pedir(`${PROGRESO_API}/progreso/${usuarioId}/patrones/`);
}

/**
 * Anota el tipo de error de un trazo fallado en la página Trazos (RF-IA-01).
 * Solo alimenta los patrones: no cambia la racha, la tasa ni el repaso.
 * `codigoError` es el `explicacion.codigo` de la evaluación (TRAZO_*).
 */
export function registrarErrorDeTrazo(usuarioId, { caracter, codigoError }) {
  return pedir(`${PROGRESO_API}/progreso/${usuarioId}/errores/`, {
    method: 'POST',
    body: JSON.stringify({ caracter, codigo_error: codigoError }),
  });
}

/**
 * Repasos del estudiante (RF-IA-02), que agenda la curva de olvido al cerrar
 * cada sesión: { usuario_id, momento, dias, vencidos, proximos }. Cada repaso
 * es { caracter, proximo_repaso, intervalo_dias, repeticiones }. `vencidos`
 * va del más atrasado al menos atrasado y `proximos` cubre los próximos
 * `dias` días; cada lista tiene como máximo `limite` repasos.
 */
export function obtenerRepasos(usuarioId, { dias = 7, limite = 20 } = {}) {
  const params = new URLSearchParams({ dias, limite });
  return pedir(`${PROGRESO_API}/progreso/${usuarioId}/repasos/?${params}`);
}

// ---------------------------------------------------------------- reportes

/**
 * Encola un reporte de progreso (tarea de Celery en reportes-flask). Responde
 * enseguida con 202 { task_id, estado: "pendiente" }: el reporte se genera en
 * segundo plano y se consulta con obtenerReporte.
 */
export function crearReporte(usuarioId) {
  return pedir(`${REPORTES_API}/reportes/`, {
    method: 'POST',
    body: JSON.stringify({ usuario_id: usuarioId }),
  });
}

/**
 * Estado del reporte: pendiente o en_proceso; listo, con `resultado`; o error,
 * con `error` (ya traducido) y `codigo`. Un 404 quiere decir que no existe o
 * que caducó (24 h).
 */
export function obtenerReporte(taskId) {
  return pedir(`${REPORTES_API}/reportes/${encodeURIComponent(taskId)}/`);
}

// ----------------------------------------------------------- suscripciones

/**
 * Planes Free y Premium (RF-USR-01): { planes: [{ codigo, nombre,
 * descripcion, precio, moneda, periodo_dias, nivel_maximo }], pasarela }.
 */
export function obtenerPlanes() {
  return pedir(`${SUSCRIPCIONES_API}/planes/`);
}

/**
 * Plan que rige hoy: { plan, nombre_plan, estado (activa | cancelada |
 * vencida), vence_en, nivel_maximo, acciones }. `acciones` dice qué se puede
 * hacer ahora (activar, renovar, cancelar). Un usuario nuevo tiene Free.
 */
export function obtenerSuscripcion(usuarioId) {
  return pedir(`${SUSCRIPCIONES_API}/${usuarioId}/`);
}

/**
 * Cobra y activa Premium. `pago` es { numero, titular, vencimiento (MM/AA),
 * cvc }. Responde { suscripcion, pago } con el pago aprobado; un 402 es una
 * tarjeta rechazada y un 503, que la pasarela no respondió (no se cobró).
 */
export function activarPremium(usuarioId, pago) {
  return pedir(`${SUSCRIPCIONES_API}/${usuarioId}/activar/`, {
    method: 'POST',
    body: JSON.stringify({ plan: 'premium', pago }),
  });
}

/** Cobra otro periodo de 30 días y lo suma al que queda. */
export function renovarPremium(usuarioId, pago) {
  return pedir(`${SUSCRIPCIONES_API}/${usuarioId}/renovar/`, {
    method: 'POST',
    body: JSON.stringify({ pago }),
  });
}

/** Sin reembolso: Premium sigue hasta `vence_en` y después vuelve a Free. */
export function cancelarPremium(usuarioId) {
  return pedir(`${SUSCRIPCIONES_API}/${usuarioId}/cancelar/`, { method: 'POST' });
}

// --------------------------------------------------------------- contenido

/**
 * El catálogo (caracteres y sus trazos) no cambia mientras se usa la app y
 * no depende del idioma, así que cada consulta se guarda en memoria durante
 * la visita: volver a Inicio o a Trazos no espera otra vez a la red. Se
 * guarda la promesa, para que dos pantallas que piden lo mismo a la vez
 * compartan una sola petición. Un error no se guarda: el siguiente intento
 * vuelve a pedir.
 */
const cacheCatalogo = new Map();

function pedirCatalogo(url) {
  if (!cacheCatalogo.has(url)) {
    const promesa = pedir(url).catch((e) => {
      cacheCatalogo.delete(url);
      throw e;
    });
    cacheCatalogo.set(url, promesa);
  }
  return cacheCatalogo.get(url);
}

export function listarCaracteres({ nivel, excluir = [], limite = 20 } = {}) {
  const params = new URLSearchParams();
  if (nivel) params.set('nivel', nivel);
  if (excluir.length) params.set('excluir', excluir.join(','));
  params.set('limite', limite);

  return pedirCatalogo(`${CATALOGO_API}/caracteres/?${params}`);
}

export function obtenerCaracter(hanzi) {
  return pedirCatalogo(`${CATALOGO_API}/caracteres/${encodeURIComponent(hanzi)}/`);
}

/** Pide un carácter en segundo plano (al pasar el puntero, o los de una sesión nueva). */
export function precargarCaracter(hanzi) {
  if (hanzi) obtenerCaracter(hanzi).catch(() => {});
}

/** Cuántos caracteres del nivel pide Inicio para elegir las palabras del día. */
export const MUESTRA_PALABRAS = 60;

/** Las palabras del día de un nivel, en segundo plano (ver App.jsx). */
export function precargarPalabras(nivel) {
  if (nivel) listarCaracteres({ nivel, limite: MUESTRA_PALABRAS }).catch(() => {});
}

/** Cuántos caracteres muestra la biblioteca de Trazos. */
export const LIMITE_BIBLIOTECA = 30;

/**
 * La biblioteca de Trazos y su primer carácter, en segundo plano: al tocar la
 * pestaña ya están en memoria y la página no espera a la red.
 */
export function precargarBiblioteca() {
  listarCaracteres({ limite: LIMITE_BIBLIOTECA })
    .then((r) => precargarCaracter(r?.caracteres?.[0]?.hanzi))
    .catch(() => {});
}

// -------------------------------------------------------------- evaluación

/**
 * Decide si una respuesta es correcta. Para un trazo, `respuesta` es
 * { secuencia, puntos, ancho, alto }: la mediana la busca el servicio en el
 * catálogo. Un 503 DEPENDENCIA_NO_DISPONIBLE quiere decir que no se pudo
 * evaluar, no que la respuesta esté mal. `dificultad` es opcional (1 a 5).
 * RF-IA-04: si falla, la respuesta trae `explicacion` { codigo, titulo,
 * porque, pista }; si un pinyin acierta, `nota` { codigo, texto } con su tono.
 */
export async function evaluar({ tipo, caracter, respuesta, dificultad }) {
  try {
    return await pedir(`${EVALUACION_API}/evaluacion/`, {
      method: 'POST',
      body: JSON.stringify({ tipo, caracter, respuesta, dificultad }),
    });
  } catch (e) {
    // 400 ENTRADA_INVALIDA / 500 ERROR_INTERNO: se muestra el código junto al mensaje.
    if (e instanceof ErrorApi && e.codigo) {
      throw new ErrorApi(`${e.message} (${e.codigo})`, e.status, e.cuerpo);
    }
    throw e;
  }
}

// ---------------------------------------------------------------- ejemplos

/**
 * Oraciones de ejemplo que usan `hanzi`, con pinyin y traducción al idioma
 * activo. Vienen de Tatoeba a través de ejemplos-flask; `atribucion` es el
 * crédito que pide su licencia. Un 503 PROVEEDOR_NO_DISPONIBLE quiere decir
 * que Tatoeba no respondió, no que el carácter no tenga ejemplos.
 */
export function obtenerEjemplos(hanzi, { limite = 3 } = {}) {
  const params = new URLSearchParams({ lang: i18n.resolvedLanguage || 'es', limite });
  return pedir(`${EJEMPLOS_API}/ejemplos/${encodeURIComponent(hanzi)}/?${params}`);
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
