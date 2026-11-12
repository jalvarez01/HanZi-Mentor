import { useEffect, useLayoutEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
// Primero los estilos globales, para que el CSS de cada página quede después en la cascada.
import './styles/tokens.css';
import './styles/components.css';
import Home from './pages/Home';
import HowItWorks from './pages/HowItWorks';
import Practica from './pages/Practica';
import Progreso from './pages/Progreso';
import Trazos from './pages/Trazos';
import TabBar from './components/TabBar';
import { ProgresoProvider } from './hooks/ProgresoContext';
import { useProgreso } from './hooks/useProgreso';
import { precargarBiblioteca, precargarPalabras } from './services/api';

// Las páginas van en un solo paquete a propósito: cada una pesa entre 3 y
// 18 KB, y separarlas le sumaba un viaje más por la red a quien entra directo
// a /practica o /trazos (unos 300 ms en 3G).

function cuandoQuedeLibre(tarea) {
  if ('requestIdleCallback' in window) requestIdleCallback(tarea, { timeout: 3000 });
  else setTimeout(tarea, 1500);
}

/**
 * Cambia de página con un fundido corto (ver .hm-ruta--entra) y la muestra
 * desde arriba. La primera carga no se anima: la página aparece apenas está
 * lista.
 */
function Paginas() {
  const { pathname, hash } = useLocation();
  const { datos: progreso } = useProgreso();
  const nivel = progreso?.nivel_hsk;
  const [inicial] = useState(pathname);
  const [navego, setNavego] = useState(false);
  if (!navego && pathname !== inicial) setNavego(true);

  // Con la página ya cargada, la biblioteca de Trazos se pide en segundo
  // plano: al tocar la pestaña ya está en memoria.
  useEffect(() => {
    const precargar = () => cuandoQuedeLibre(precargarBiblioteca);
    if (document.readyState === 'complete') precargar();
    else window.addEventListener('load', precargar, { once: true });
  }, []);

  // Las palabras del día dependen del nivel: se piden apenas se conoce.
  useEffect(() => {
    if (nivel) cuandoQuedeLibre(() => precargarPalabras(nivel));
  }, [nivel]);

  // El navegador conserva el scroll de la página anterior: sin esto, venir
  // desde abajo de Progreso deja Trazos a mitad de camino. Con #ancla (por
  // ejemplo /progreso#plan) la página hace su propio desplazamiento.
  useLayoutEffect(() => {
    if (navego && !hash) window.scrollTo(0, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <div key={pathname} className={navego ? 'hm-ruta hm-ruta--entra' : 'hm-ruta'}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/como-funciona" element={<HowItWorks />} />
        <Route path="/trazos" element={<Trazos />} />
        <Route path="/practica" element={<Practica />} />
        <Route path="/tutor" element={<Practica />} />
        <Route path="/progreso" element={<Progreso />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      {/* Dentro del router: refresca el progreso al cambiar de ruta. */}
      <ProgresoProvider>
        <div className="app-shell">
          <div className="hm-ink-wash hm-ink-wash--jade" aria-hidden="true" />
          <div className="hm-ink-wash hm-ink-wash--cinnabar" aria-hidden="true" />
          <Paginas />
          <TabBar />
        </div>
      </ProgresoProvider>
    </BrowserRouter>
  );
}
