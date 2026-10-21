import { obtenerProgreso } from '../services/api';
import { useAsync } from './useAsync';
import { useUsuario } from './useUsuario';

/**
 * Progreso del usuario actual (agente-tutor), con su estado de carga.
 *
 * Cada pantalla monta su propia instancia: al navegar se vuelve a pedir,
 * así la racha y el nivel se ven al día después de practicar.
 */
export function useProgreso() {
  const { usuarioId, reiniciar } = useUsuario();
  const estado = useAsync(
    () => obtenerProgreso(usuarioId),
    [usuarioId],
    Boolean(usuarioId),
  );

  return { usuarioId, reiniciar, ...estado };
}

/** Mayor cantidad de aciertos seguidos en un mismo carácter. */
export function mejorRacha(progreso) {
  const rachas = Object.values(progreso?.aciertos_consecutivos || {});
  return rachas.length ? Math.max(...rachas) : 0;
}
