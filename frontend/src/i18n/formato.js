import { useTranslation } from 'react-i18next';

/**
 * Formatos dependientes del idioma (Intl), ligados al idioma activo.
 * Al cambiar de idioma el componente se vuelve a renderizar con los nuevos formatos.
 */
export function useFormato() {
  const { i18n } = useTranslation();
  const idioma = i18n.resolvedLanguage || 'es';

  return {
    /** 0.72 -> "72 %" (es) / "72%" (en) */
    porcentaje(valor) {
      return new Intl.NumberFormat(idioma, { style: 'percent', maximumFractionDigits: 0 }).format(valor ?? 0);
    },

    /** Fecha y hora media: "21 oct 2026, 17:30" / "Oct 21, 2026, 5:30 PM" */
    fechaHora(iso) {
      return new Intl.DateTimeFormat(idioma, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso));
    },

    /**
     * Tiempo relativo hasta una fecha: en horas si falta menos de un día,
     * en días si no ("dentro de 5 horas" / "in 3 days"). null -> null.
     */
    relativo(iso) {
      if (!iso) return null;

      const horas = Math.round((new Date(iso) - new Date()) / 36e5);
      const rtf = new Intl.RelativeTimeFormat(idioma, { numeric: 'always' });

      if (horas < 24) return rtf.format(horas, 'hour');
      return rtf.format(Math.round(horas / 24), 'day');
    },

    /**
     * Tiempo relativo desde una fecha pasada, en minutos, horas o días:
     * "hace 5 minutos", "hace 3 horas", "ayer", "hace 4 días" / "5 minutes
     * ago", "yesterday". Menos de un minuto: "ahora" / "now". null -> null.
     */
    hace(iso) {
      if (!iso) return null;

      const minutos = Math.max(0, Math.round((new Date() - new Date(iso)) / 6e4));
      const rtf = new Intl.RelativeTimeFormat(idioma, { numeric: 'auto' });

      if (minutos < 1) return rtf.format(0, 'second');
      if (minutos < 60) return rtf.format(-minutos, 'minute');
      if (minutos < 24 * 60) return rtf.format(-Math.round(minutos / 60), 'hour');
      return rtf.format(-Math.round(minutos / (24 * 60)), 'day');
    },
  };
}
