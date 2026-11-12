import { useCallback, useEffect, useRef, useState } from 'react';
import i18n from '../i18n';
import { crearReporte, obtenerReporte } from '../services/api';

// Cada cuánto se pregunta el estado. Un reporte normal está listo en menos
// de medio segundo, así que las primeras consultas son seguidas y después se
// espacian hasta INTERVALO_MS. El peor caso del servicio (progreso caído, con
// los reintentos de Celery) ronda los 23 s: después de 45 s sin respuesta
// final se deja de preguntar y se muestra el error.
const PRIMERAS_ESPERAS_MS = [250, 250, 500, 1000];
const INTERVALO_MS = 2000;
const ESPERA_MAXIMA_MS = 45000;

/**
 * Genera un reporte de progreso en segundo plano (T20) y sigue su estado.
 *
 * `estado` es 'inactivo', 'pendiente', 'en_proceso', 'listo' (con
 * `resultado`) o 'error' (con `error`). Al desmontar, o al pedir otro
 * reporte, deja de consultar el anterior.
 */
export function useReporte(usuarioId) {
  const [reporte, setReporte] = useState({ estado: 'inactivo' });
  const temporizador = useRef(null);
  // Número de la generación vigente: una respuesta de otra se descarta.
  const generacion = useRef(0);

  const detener = useCallback(() => {
    clearTimeout(temporizador.current);
    temporizador.current = null;
  }, []);

  useEffect(
    () => () => {
      generacion.current += 1;
      detener();
    },
    [detener],
  );

  const generar = useCallback(async () => {
    detener();
    const actual = ++generacion.current;
    const vigente = () => actual === generacion.current;
    const inicio = Date.now();
    const fallar = (mensaje) => {
      if (vigente()) setReporte({ estado: 'error', error: mensaje || i18n.t('common.genericError') });
    };

    setReporte({ estado: 'pendiente' });
    let consultas = 0;
    const siguienteEspera = () => PRIMERAS_ESPERAS_MS[consultas++] ?? INTERVALO_MS;

    let taskId;
    try {
      ({ task_id: taskId } = await crearReporte(usuarioId));
    } catch (e) {
      fallar(e.message);
      return;
    }

    const consultar = async () => {
      if (!vigente()) return;
      try {
        const r = await obtenerReporte(taskId);
        if (!vigente()) return;
        if (r.estado === 'listo') {
          setReporte({ estado: 'listo', resultado: r.resultado });
          return;
        }
        if (r.estado === 'error') {
          fallar(r.error);
          return;
        }
        setReporte({ estado: r.estado });
      } catch (e) {
        fallar(e.message);
        return;
      }

      if (Date.now() - inicio > ESPERA_MAXIMA_MS) {
        fallar(i18n.t('report.timeout'));
        return;
      }
      temporizador.current = setTimeout(consultar, siguienteEspera());
    };

    temporizador.current = setTimeout(consultar, siguienteEspera());
  }, [usuarioId, detener]);

  return { ...reporte, generar };
}
