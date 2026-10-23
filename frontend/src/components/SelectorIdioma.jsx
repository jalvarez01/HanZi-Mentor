import { useTranslation } from 'react-i18next';
import { IDIOMAS } from '../i18n';
import './SelectorIdioma.css';

/**
 * Par de botones conmutables (es / en). aria-pressed indica el activo y
 * cada botón anuncia el nombre completo del idioma en ese mismo idioma.
 */
export default function SelectorIdioma() {
  const { t, i18n } = useTranslation();
  const actual = i18n.resolvedLanguage;

  return (
    <div className="selector-idioma" role="group" aria-label={t('language.label')}>
      {IDIOMAS.map((idioma) => (
        <button
          key={idioma}
          type="button"
          lang={idioma}
          className="selector-idioma__opcion"
          aria-pressed={actual === idioma}
          aria-label={t(`language.${idioma}`)}
          onClick={() => i18n.changeLanguage(idioma)}
        >
          {idioma.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
