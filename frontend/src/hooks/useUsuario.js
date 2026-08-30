import { useEffect, useState } from 'react';

const CLAVE = 'hanzi-mentor:usuario-id';

/**
 * Identidad temporal del usuario.
 *
 * El servicio `usuarios` todavía no existe, así que generamos un UUID local
 * y lo guardamos en el navegador. Cuando haya login de verdad, este hook se
 * reemplaza por uno que lea el token de sesión — el resto de la app no cambia.
 */
export function useUsuario() {
  const [usuarioId, setUsuarioId] = useState(null);

  useEffect(() => {
    let guardado = localStorage.getItem(CLAVE);

    if (!guardado) {
      guardado = crypto.randomUUID();
      localStorage.setItem(CLAVE, guardado);
    }

    setUsuarioId(guardado);
  }, []);

  const reiniciar = () => {
    const nuevo = crypto.randomUUID();
    localStorage.setItem(CLAVE, nuevo);
    setUsuarioId(nuevo);
  };

  return { usuarioId, reiniciar };
}
