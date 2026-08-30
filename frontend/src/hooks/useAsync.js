import { useCallback, useEffect, useState } from 'react';

/**
 * Ejecuta una función asíncrona y expone su estado.
 *
 * Evita repetir el trío cargando/error/datos en cada pantalla.
 * `dependencias` funciona como en useEffect: si cambian, se vuelve a pedir.
 */
export function useAsync(funcion, dependencias = [], activo = true) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(activo);
  const [error, setError] = useState(null);

  const ejecutar = useCallback(async () => {
    setCargando(true);
    setError(null);

    try {
      setDatos(await funcion());
    } catch (e) {
      setError(e.message || 'Algo salió mal');
    } finally {
      setCargando(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencias);

  useEffect(() => {
    if (activo) ejecutar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ejecutar, activo]);

  return { datos, cargando, error, recargar: ejecutar, setDatos };
}
