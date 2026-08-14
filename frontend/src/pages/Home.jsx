import { Link } from 'react-router-dom';
import TopBar from '../components/TopBar';
import './Home.css';

const CARDS = [
  {
    to: '/trazos',
    num: '壹',
    title: 'Trazos guiados',
    desc: 'Dibujá con el dedo y recibí corrección trazo por trazo.',
    color: 'var(--seal)',
  },
  {
    to: '/tutor',
    num: '贰',
    title: 'Tutor adaptativo',
    desc: 'Ejercicios generados a partir de tus errores reales.',
    color: 'var(--jade)',
  },
  {
    to: '/progreso',
    num: '叁',
    title: 'Progreso por niveles',
    desc: 'HSK 1 a 6 con repaso espaciado según tu curva de olvido.',
    color: 'var(--gold)',
  },
];

export default function Home() {
  return (
    <>
      <TopBar title="HanZi Mentor" />

      <section className="hero">
        <div className="hero-char-box">
          <div className="ink-wash" />
          <div className="hero-char">学</div>
        </div>

        <h2 className="hero-title">
          Aprende mandarín<br />
          trazo a <span className="accent">trazo</span>.
        </h2>

        <p className="hero-sub">
          Un tutor con IA que detecta en qué caracteres te equivocás y ajusta
          cada lección a tu ritmo.
        </p>
      </section>

      <div className="divider" />

      <section className="cards screen-pad">
        {CARDS.map((c) => (
          <Link key={c.to} to={c.to} className="card">
            <span className="card-num" style={{ color: c.color }}>{c.num}</span>
            <div className="card-body">
              <h3>{c.title}</h3>
              <p>{c.desc}</p>
            </div>
            <span className="card-chev">›</span>
          </Link>
        ))}
      </section>

      <section className="screen-pad cta-block">
        <Link to="/trazos" className="btn-primary">Empezar a practicar</Link>
        <Link to="/como-funciona" className="btn-text">Ver cómo funciona</Link>
      </section>
    </>
  );
}
