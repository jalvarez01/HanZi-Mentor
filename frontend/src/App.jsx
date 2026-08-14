import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import HowItWorks from './pages/HowItWorks';
import Placeholder from './pages/Placeholder';
import TabBar from './components/TabBar';
import './styles/tokens.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/como-funciona" element={<HowItWorks />} />
          <Route path="/trazos" element={
            <Placeholder title="Trazos" glyph="写"
              note="Aquí va el lienzo de práctica de trazos." />
          } />
          <Route path="/tutor" element={
            <Placeholder title="Tutor IA" glyph="师"
              note="Aquí va la sesión con el agente tutor." />
          } />
          <Route path="/progreso" element={
            <Placeholder title="Progreso" glyph="级"
              note="Aquí van tus estadísticas y niveles HSK." />
          } />
        </Routes>
        <TabBar />
      </div>
    </BrowserRouter>
  );
}
