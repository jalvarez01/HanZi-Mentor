import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import HowItWorks from './pages/HowItWorks';
import Practica from './pages/Practica';
import Progreso from './pages/Progreso';
import Trazos from './pages/Trazos';
import TabBar from './components/TabBar';
import './styles/tokens.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
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
    </BrowserRouter>
  );
}
