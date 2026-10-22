import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import i18n from '../i18n';
import { obtenerProgreso } from '../services/api';
import { ProgresoContext } from './progresoContexto';
import { useUsuario } from './useUsuario';

const INICIAL = { datos: null, cargando: true, error: null };

/**
 * Estado de progreso compartido (agente-tutor).
 *
 * - Una sola petición por navegación, que comparten el TopBar y la página.
 * - Al cambiar de ruta se refresca en segundo plano: los datos anteriores se
 *   mantienen visibles (sin parpadeo de "cargando") hasta que llega la respuesta.
 * - `reiniciar` cambia de usuario y descarta los datos del anterior.
 */
export function ProgresoProvider({ children }) {
  const { usuarioId, reiniciar } = useUsuario();
  const { pathname } = useLocation();
  const [estado, setEstado] = useState(INICIAL);

  // Descarta respuestas que llegan tarde (de un usuario o petición anterior).
  const ultimaPeticion = useRef(0);
  const usuarioCargado = useRef(null);

  const recargar = useCallback(async () => {
    if (!usuarioId) return;

    const peticion = ++ultimaPeticion.current;
    const esOtroUsuario = usuarioCargado.current !== usuarioId;

    setEstado((previo) => ({
      datos: esOtroUsuario ? null : previo.datos,
      cargando: esOtroUsuario || previo.datos === null,
      error: null,
    }));

    try {
      const datos = await obtenerProgreso(usuarioId);
      if (peticion !== ultimaPeticion.current) return;
      usuarioCargado.current = usuarioId;
      setEstado({ datos, cargando: false, error: null });
    } catch (e) {
      if (peticion !== ultimaPeticion.current) return;
      // Como useAsync: se conserva el último dato válido y se informa el error.
      setEstado((previo) => ({ ...previo, cargando: false, error: e.message || i18n.t('common.genericError') }));
    }
  }, [usuarioId]);

  useEffect(() => {
    recargar();
  }, [recargar, pathname]);

  const valor = useMemo(
    () => ({ ...estado, usuarioId, reiniciar, recargar }),
    [estado, usuarioId, reiniciar, recargar],
  );

  return <ProgresoContext.Provider value={valor}>{children}</ProgresoContext.Provider>;
}
