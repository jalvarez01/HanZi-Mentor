import { obtenerSuscripcion } from '../services/api';
import { useAsync } from './useAsync';

/** Último nivel HSK: lo que se abre si no se puede confirmar el plan. */
export const NIVEL_MAXIMO = 6;

/**
 * Plan del usuario en suscripciones-flask (RF-USR-01).
 *
 * `nivelMaximo` es el último nivel que deja practicar el plan. Si el servicio
 * no responde no se bloquea ningún nivel (modo degradado): mejor dejar
 * practicar de más que cerrarle HSK 4 a 6 a alguien que pagó. En ese caso
 * `sinConfirmar` es true para avisarlo. Mientras carga, `nivelMaximo` es
 * null y tampoco se bloquea nada.
 */
export function useSuscripcion(usuarioId) {
  const { datos, cargando, error, recargar, setDatos } = useAsync(
    () => obtenerSuscripcion(usuarioId),
    [usuarioId],
    Boolean(usuarioId),
  );

  let nivelMaximo = null;
  if (datos) nivelMaximo = datos.nivel_maximo;
  else if (error) nivelMaximo = NIVEL_MAXIMO;

  return {
    suscripcion: datos,
    setSuscripcion: setDatos,
    cargando,
    error,
    recargar,
    nivelMaximo,
    sinConfirmar: Boolean(error) && !datos,
  };
}
