import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import TopBar from '../components/TopBar';
import './HowItWorks.css';

function Bar({ value, color }) {
  return (
    <div className="pb-track">
      <div className="pb-fill" style={{ width: `${value * 100}%`, background: color }} />
    </div>
  );
}

function Step({ id, mark, title, color, children }) {
  return (
    <section className="step" id={id}>
      <div className="step-mark" style={{ color }}>
        <span>{mark}</span>
        <i style={{ background: color }} />
      </div>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export default function HowItWorks() {
  const { hash } = useLocation();

  useEffect(() => {
    if (hash) {
      const el = document.querySelector(hash);
      if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
    } else {
      window.scrollTo(0, 0);
    }
  }, [hash]);

  return (
    <>
      <TopBar title="Cómo funciona" back />

      <div className="screen-pad hiw">
        <p className="hiw-intro">
          Tres piezas trabajando juntas: lo que dibujás, lo que el tutor aprende
          de vos, y cuándo te toca repasar.
        </p>

        <Step id="trazos" mark="壹 · 01" title="Trazos guiados" color="var(--seal)">
          <p className="body-text">
            Dibujás el carácter con el dedo. El sistema compara, trazo por trazo,
            tu orden y dirección contra el correcto.
          </p>

          <div className="demo-row">
            <div className="demo-card">
              <div className="demo-char" style={{ borderColor: 'var(--jade)' }}>人</div>
              <span style={{ color: 'var(--jade)' }}>Correcto</span>
            </div>
            <div className="demo-card">
              <div className="demo-char" style={{ borderColor: 'var(--seal)' }}>入</div>
              <span style={{ color: 'var(--seal)' }}>Trazo invertido</span>
            </div>
          </div>

          <ul className="bullets">
            <li>Feedback inmediato mientras dibujás.</li>
            <li>Secuencia oficial de trazos desde datasets abiertos (Hanzi Writer).</li>
          </ul>
        </Step>

        <Step id="tutor" mark="贰 · 02" title="Tutor adaptativo" color="var(--jade)">
          <p className="body-text">
            Un agente de IA analiza tu historial: qué caracteres confundís seguido
            y en qué tipo de trazo fallás más.
          </p>

          <div className="demo-panel">
            <div className="demo-line">
              <span className="hanzi-inline">目 vs 且</span>
              <span style={{ color: 'var(--seal)' }}>6 confusiones</span>
            </div>
            <Bar value={0.75} color="var(--seal)" />

            <div className="demo-line">
              <span className="hanzi-inline">氵 radical agua</span>
              <span style={{ color: 'var(--jade)' }}>dominado</span>
            </div>
            <Bar value={0.95} color="var(--jade)" />
          </div>

          <ul className="bullets">
            <li>Prioriza justo lo que te cuesta, no listas al azar.</li>
            <li>Explica el error en lenguaje simple.</li>
          </ul>
        </Step>

        <Step id="progreso" mark="叁 · 03" title="Progreso por niveles" color="var(--gold)">
          <p className="body-text">
            Avanzás de HSK 1 a HSK 6. El sistema calcula tu curva de olvido y
            decide cuándo repasar cada carácter.
          </p>

          <div className="levels">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div key={n} className={`level ${n <= 2 ? 'active' : ''}`}>HSK{n}</div>
            ))}
          </div>

          <ul className="bullets">
            <li>Repaso justo antes de que lo olvides, no todos los días.</li>
          </ul>
        </Step>
      </div>
    </>
  );
}
