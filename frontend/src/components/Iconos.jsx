/**
 * Iconos SVG en línea (sin dependencias). Heredan el color con currentColor
 * y son decorativos: el texto accesible lo pone el control que los contiene.
 */

function Icono({ children, relleno = 'none', ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={relleno}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export function IconoLlama(props) {
  return (
    // Silueta rellena con una lengua interior calada (evenodd); sin trazo para que el calado se vea a 16 px.
    <Icono relleno="currentColor" stroke="none" {...props}>
      <path
        fillRule="evenodd"
        d="M12 1.5c.4 2.6 2 4.3 3.6 6 1.6 1.8 3.4 3.8 3.4 7a7 7 0 0 1-14 0c0-2.6 1.2-4.5 2.6-6 .2 1.8 1 3 2.2 3.6C9.4 9 10 5 12 1.5zM12 21a3 3 0 0 0 3-3c0-1.8-1.3-2.8-2.2-4.2-.4 1.2-1.1 2-2 2.4.1-.9 0-1.7-.4-2.5C9.6 14.6 9 15.8 9 18a3 3 0 0 0 3 3z"
      />
    </Icono>
  );
}

export function IconoAtras(props) {
  return (
    <Icono {...props}>
      <path d="M15 18l-6-6 6-6" />
    </Icono>
  );
}

export function IconoInicio(props) {
  return (
    <Icono {...props}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9v12h14V9" />
      <path d="M10 21v-6h4v6" />
    </Icono>
  );
}

export function IconoTrazos(props) {
  return (
    <Icono {...props}>
      <path d="M16 3.5 20.5 8 9 19.5H4.5V15z" />
      <path d="M13.5 6 18 10.5" />
    </Icono>
  );
}

export function IconoPracticar(props) {
  return (
    <Icono {...props}>
      <path d="M21 12a8.5 8.5 0 0 1-12.4 7.5L3.5 21l1.5-5A8.5 8.5 0 1 1 21 12z" />
    </Icono>
  );
}

export function IconoProgreso(props) {
  return (
    <Icono {...props}>
      <path d="M8 4h8v5a4 4 0 0 1-8 0z" />
      <path d="M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4" />
      <path d="M12 13v4M8 21h8M10 17h4v4h-4z" />
    </Icono>
  );
}
