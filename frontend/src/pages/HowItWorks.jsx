import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import TopBar from '../components/TopBar';
import './HowItWorks.css';

function Bar({ value, tono }) {
  return (
    <div className="pb-track" aria-hidden="true">
      <div className={`pb-fill pb-fill--${tono}`} style={{ width: `${value * 100}%` }} />
    </div>
  );
}

function Step({ id, mark, title, tono, children }) {
  return (
    <section className={`hm-panel step step--${tono}`} id={id} aria-labelledby={`${id}-titulo`}>
      <div className="step-mark">
        <span>{mark}</span>
        <i />
      </div>
      <h2 id={`${id}-titulo`}>{title}</h2>
      {children}
    </section>
  );
}

function Puntos({ items }) {
  return (
    <ul className="bullets">
      {items.map((texto) => <li key={texto}>{texto}</li>)}
    </ul>
  );
}

export default function HowItWorks() {
  const { hash } = useLocation();
  const { t } = useTranslation();

  useEffect(() => {
    if (hash) {
      const el = document.querySelector(hash);
      // Sin animación si el usuario pidió reducir el movimiento.
      const reducir = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      if (el) setTimeout(() => el.scrollIntoView({ behavior: reducir ? 'auto' : 'smooth', block: 'start' }), 120);
    } else {
      window.scrollTo(0, 0);
    }
  }, [hash]);

  const lista = (clave) => t(clave, { returnObjects: true });

  return (
    <>
      <TopBar title={t('howItWorks.title')} back />

      <div className="hm-page hiw">
        <p className="hiw-intro">{t('howItWorks.intro')}</p>

        <Step id="trazos" mark="壹 · 01" title={t('howItWorks.strokes.title')} tono="cinnabar">
          <p className="body-text">{t('howItWorks.strokes.text')}</p>

          <div className="demo-row">
            <div className="demo-card demo-card--jade">
              <div className="demo-char" lang="zh-Hans">人</div>
              <span>{t('howItWorks.strokes.demoCorrect')}</span>
            </div>
            <div className="demo-card demo-card--cinnabar">
              <div className="demo-char" lang="zh-Hans">入</div>
              <span>{t('howItWorks.strokes.demoReversed')}</span>
            </div>
          </div>

          <Puntos items={lista('howItWorks.strokes.bullets')} />
        </Step>

        <Step id="tutor" mark="贰 · 02" title={t('howItWorks.tutor.title')} tono="jade">
          <p className="body-text">{t('howItWorks.tutor.text')}</p>

          <div className="demo-panel">
            <div className="demo-line">
              <span className="hanzi-inline">{t('howItWorks.tutor.demoConfusion')}</span>
              <span className="demo-line__valor--cinnabar">{t('howItWorks.tutor.demoConfusionValue')}</span>
            </div>
            <Bar value={0.75} tono="cinnabar" />

            <div className="demo-line">
              <span className="hanzi-inline">{t('howItWorks.tutor.demoRadical')}</span>
              <span className="demo-line__valor--jade">{t('howItWorks.tutor.demoRadicalValue')}</span>
            </div>
            <Bar value={0.95} tono="jade" />
          </div>

          <Puntos items={lista('howItWorks.tutor.bullets')} />
        </Step>

        <Step id="progreso" mark="叁 · 03" title={t('howItWorks.progress.title')} tono="ochre">
          <p className="body-text">{t('howItWorks.progress.text')}</p>

          <div className="levels">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div key={n} className={`level ${n <= 2 ? 'active' : ''}`}>HSK{n}</div>
            ))}
          </div>

          <Puntos items={lista('howItWorks.progress.bullets')} />
        </Step>
      </div>
    </>
  );
}
