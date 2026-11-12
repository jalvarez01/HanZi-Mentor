import { lazy, Suspense, useEffect, useLayoutEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
// Primero los estilos globales, para que el CSS de cada página quede después en la cascada.
import './styles/tokens.css';
import './styles/components.css';
import Home from './pages/Home';
import TabBar from './components/TabBar';
import TopBar from './components/TopBar';
import { ProgresoProvider } from './hooks/ProgresoContext';
import { useProgreso } from './hooks/useProgreso';
import { precargarBiblioteca, precargarPalabras } from './services/api';

// Inicio va en el paquete principal: es la primera pantalla. Las demás se
// bajan aparte y se precargan cuando el navegador queda libre, junto con los
// datos de la biblioteca de Trazos, así que al tocar una pestaña ya están
// (ver precargarRutas).
const cargarComoFunciona = () => import('./pages/HowItWorks');
const cargarPractica = () => import('./pages/Practica');
const cargarProgreso = () => import('./pages/Progreso');
const cargarTrazos = () => import('./pages/Trazos');

const HowItWorks = lazy(cargarComoFunciona);
const Practica = lazy(cargarPractica);
const Progreso = lazy(cargarProgreso);
const Trazos = lazy(cargarTrazos);

function cuandoQuedeLibre(tarea) {
  if ('requestIdleCallback' in window) requestIdleCallback(tarea, { timeout: 3000 });
  else setTimeout(tarea, 1500);
}

function precargarRutas() {
  cuandoQuedeLibre(() => {
    for (const cargar of [cargarPractica, cargarTrazos, cargarProgreso, cargarComoFunciona]) {
      cargar().catch(() => {});
    }
    precargarBiblioteca();
  });
}

/** Mientras baja el código de una página (solo si se toca antes de la precarga). */
function RutaCargando() {
  const { t } = useTranslation();
  return (
    <>
      <TopBar />
      <main className="hm-page" aria-busy="true">
        <p className="hm-status hm-status--loading" role="status">{t('common.loading')}</p>
      </main>
    </>
  );
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

  useEffect(() => {
    if (document.readyState === 'complete') precargarRutas();
    else window.addEventListener('load', precargarRutas, { once: true });
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
      <Suspense fallback={<RutaCargando />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/como-funciona" element={<HowItWorks />} />
          <Route path="/trazos" element={<Trazos />} />
          <Route path="/practica" element={<Practica />} />
          <Route path="/tutor" element={<Practica />} />
          <Route path="/progreso" element={<Progreso />} />
        </Routes>
      </Suspense>
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
