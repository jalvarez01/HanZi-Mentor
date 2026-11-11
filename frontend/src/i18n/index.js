import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';
import es from './locales/es.json';
import en from './locales/en.json';

export const IDIOMAS = ['es', 'en'];
const CLAVE = 'hanzi-mentor:idioma';

/**
 * Detector propio sobre localStorage.
 *
 * El del paquete solo verifica que localStorage exista; en modo privado o
 * con la cuota llena setItem también puede fallar, así que cada acceso va
 * envuelto en try/catch y, si falla, se sigue con el idioma por defecto.
 */
const almacen = {
  name: 'almacen',
  lookup() {
    try {
      return localStorage.getItem(CLAVE) || undefined;
    } catch {
      return undefined;
    }
  },
  cacheUserLanguage(idioma) {
    try {
      localStorage.setItem(CLAVE, idioma);
    } catch {
      // Sin almacenamiento el idioma dura solo esta sesión.
    }
  },
};

const detector = new LanguageDetector();
detector.addDetector(almacen);

function sincronizarLang(idioma) {
  document.documentElement.lang = idioma || 'es';
}

i18n.on('languageChanged', sincronizarLang);

i18n
  .use(detector)
  .use(initReactI18next)
  .init({
    resources: {
      es: { translation: es },
      en: { translation: en },
    },
    supportedLngs: IDIOMAS,
    fallbackLng: 'es',
    load: 'languageOnly',
    // Sin elección guardada se usa español: no se consulta el navegador.
    detection: {
      order: ['almacen'],
      caches: ['almacen'],
    },
    interpolation: { escapeValue: false },
  });

sincronizarLang(i18n.resolvedLanguage);

export default i18n;
