import { useTranslation } from 'react-i18next';
import './PorQue.css';

/**
 * Bloque "Por qué" (RF-IA-04): explica un error y da la pista para el
 * siguiente intento, debajo del veredicto.
 *
 * `explicacion` llega de evaluacion-flask ya traducida: { codigo, titulo,
 * porque, pista }. Sin ella, `pista` muestra un texto fijo de la interfaz.
 * `anunciar` lo vuelve región viva, para cuando el veredicto de arriba no
 * lo es; `children` va al final (por ejemplo, un enlace).
 */
export default function PorQue({ explicacion, pista, anunciar = false, children }) {
  const { t } = useTranslation();
  const textoPista = explicacion?.pista || pista;

  if (!explicacion && !pista) return null;

  return (
    <div className="por-que" role={anunciar ? 'status' : undefined} data-codigo={explicacion?.codigo}>
      <p className="hm-kicker por-que__etiqueta">{t('feedback.why')}</p>
      {explicacion?.titulo && <p className="por-que__titulo">{explicacion.titulo}</p>}
      {explicacion?.porque && <p className="por-que__texto">{explicacion.porque}</p>}
      {textoPista && (
        <p className="por-que__pista">
          <strong>{t('feedback.hint')}</strong> {textoPista}
        </p>
      )}
      {children}
    </div>
  );
}
