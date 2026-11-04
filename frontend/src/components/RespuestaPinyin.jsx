import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { evaluar } from '../services/api';
import './RespuestaPinyin.css';

const MAXIMO = 30;
// Letras del pinyin, vocales con tono, ü (o v), números de tono, espacios y apóstrofo.
const PERMITIDOS = /^[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü'’\s1-5]+$/i;

/**
 * Normaliza lo que escribió el estudiante antes de enviarlo: minúsculas,
 * espacios simples, `v` como `ü` y sin números de tono. evaluacion-flask
 * compara sin tonos, así que "ren2", "Ren" y "rén" valen igual.
 */
function normalizarPinyin(texto) {
  return texto
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/v/g, 'ü')
    .replace(/[1-5]/g, '');
}

/** Devuelve la clave del error de validación, o null si el texto es válido. */
function validarPinyin(texto) {
  const limpio = texto.trim();
  if (!limpio) return 'pinyinForm.required';
  if (limpio.length > MAXIMO) return 'pinyinForm.tooLong';
  if (!PERMITIDOS.test(limpio)) return 'pinyinForm.invalidChars';
  return null;
}

/**
 * Formulario para responder un ejercicio escribiendo el pinyin del carácter
 * (T25). Lo valida en el cliente, lo evalúa evaluacion-flask (que vuelve a
 * validarlo) y le pasa el resultado a `onResponder`, que lo registra en la
 * sesión.
 *
 * Si algo falla, el texto escrito se conserva para reintentar, y no se puede
 * enviar dos veces mientras hay un envío en curso.
 */
export default function RespuestaPinyin({ caracter, onResponder }) {
  const { t } = useTranslation();
  const [valor, setValor] = useState('');
  const [errorCampo, setErrorCampo] = useState(null);
  const [errorEnvio, setErrorEnvio] = useState(null);
  const [enviando, setEnviando] = useState(false);
  // Además del estado: bloquea un segundo Enter antes de que React vuelva a pintar.
  const enviandoRef = useRef(false);
  const campoRef = useRef(null);

  async function ejecutar(accion) {
    if (enviandoRef.current) return;
    enviandoRef.current = true;
    setEnviando(true);
    setErrorEnvio(null);

    try {
      await accion();
    } catch (e) {
      // Los servicios mandan `error` ya traducido; evaluar() le suma el código al mensaje.
      const mensaje = e.cuerpo?.error || e.message;
      if (e.codigo === 'ENTRADA_INVALIDA') {
        setErrorCampo(mensaje);
        campoRef.current?.focus();
      } else {
        setErrorEnvio(mensaje);
      }
    } finally {
      enviandoRef.current = false;
      setEnviando(false);
    }
  }

  function enviar(evento) {
    evento.preventDefault();

    const problema = validarPinyin(valor);
    if (problema) {
      setErrorCampo(t(problema, { maximo: MAXIMO }));
      campoRef.current?.focus();
      return;
    }

    ejecutar(async () => {
      const respuesta = normalizarPinyin(valor);
      const { acerto } = await evaluar({ tipo: 'pinyin', caracter, respuesta });
      await onResponder({ acerto, respuesta });
    });
  }

  function noLoSe() {
    setErrorCampo(null);
    ejecutar(() => onResponder({ acerto: false, respuesta: null }));
  }

  const describidoPor = errorCampo ? 'pinyin-ayuda pinyin-error' : 'pinyin-ayuda';

  return (
    <form className="hm-panel respuesta-pinyin" onSubmit={enviar} noValidate>
      <label htmlFor="pinyin-campo" className="respuesta-pinyin__etiqueta">
        {t('pinyinForm.label')}
      </label>
      <p id="pinyin-ayuda" className="respuesta-pinyin__ayuda">{t('pinyinForm.help')}</p>

      <input
        id="pinyin-campo"
        ref={campoRef}
        className="respuesta-pinyin__campo"
        type="text"
        value={valor}
        onChange={(e) => {
          setValor(e.target.value);
          if (errorCampo) setErrorCampo(null);
        }}
        maxLength={MAXIMO}
        autoComplete="off"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        readOnly={enviando}
        aria-invalid={Boolean(errorCampo)}
        aria-describedby={describidoPor}
      />

      {errorCampo && (
        <p id="pinyin-error" className="respuesta-pinyin__error" role="alert">{errorCampo}</p>
      )}
      {errorEnvio && <p className="hm-status hm-status--error" role="alert">{errorEnvio}</p>}

      <div className="respuesta-pinyin__acciones">
        <button type="button" className="hm-btn" onClick={noLoSe} disabled={enviando}>
          {t('pinyinForm.dontKnow')}
        </button>
        <button type="submit" className="hm-btn hm-btn--jade" disabled={enviando}>
          {enviando ? t('pinyinForm.checking') : t('pinyinForm.check')}
        </button>
      </div>
    </form>
  );
}
