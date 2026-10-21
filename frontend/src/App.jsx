import { BrowserRouter, Routes, Route } from 'react-router-dom';
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

export default function App() {
  return (
    <BrowserRouter>
      {/* Dentro del router: refresca el progreso al cambiar de ruta. */}
      <ProgresoProvider>
        <div className="app-shell">
          <div className="hm-ink-wash hm-ink-wash--jade" aria-hidden="true" />
          <div className="hm-ink-wash hm-ink-wash--cinnabar" aria-hidden="true" />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/como-funciona" element={<HowItWorks />} />
            <Route path="/trazos" element={<Trazos />} />
            <Route path="/practica" element={<Practica />} />
            <Route path="/tutor" element={<Practica />} />
            <Route path="/progreso" element={<Progreso />} />
          </Routes>
          <TabBar />
        </div>
      </ProgresoProvider>
    </BrowserRouter>
  );
}
