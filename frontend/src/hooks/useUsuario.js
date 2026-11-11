import { useEffect, useState } from 'react';

const CLAVE = 'hanzi-mentor:usuario-id';

/**
 * UUID v4. crypto.randomUUID solo existe en contexto seguro (HTTPS o
 * localhost): servida por http://<IP>, como en EC2 sin certificado, no está
 * y la app quedaba en blanco. getRandomValues sí existe en los dos casos.
 */
function nuevoUuid() {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; // versión 4
  b[8] = (b[8] & 0x3f) | 0x80; // variante RFC 4122
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

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
      guardado = nuevoUuid();
      localStorage.setItem(CLAVE, guardado);
    }

    setUsuarioId(guardado);
  }, []);

  const reiniciar = () => {
    const nuevo = nuevoUuid();
    localStorage.setItem(CLAVE, nuevo);
    setUsuarioId(nuevo);
  };

  return { usuarioId, reiniciar };
}
