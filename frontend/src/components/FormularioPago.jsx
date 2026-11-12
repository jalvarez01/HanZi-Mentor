import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

const VACIO = { titular: '', numero: '', vencimiento: '', cvc: '' };
const CAMPOS = ['titular', 'numero', 'vencimiento', 'cvc'];
const VENCIMIENTO = /^(\d{2})\s*\/\s*(\d{2})$/;

/**
 * Formato mientras se escribe. El teclado numérico de iOS (inputMode
 * numeric) no tiene espacio ni "/", así que el campo los pone solo: el
 * número en grupos de 4 y el vencimiento como MM/AA. Cualquier otro
 * carácter se descarta.
 */
const FORMATOS = {
  numero: (texto) => texto.replace(/\D/g, '').slice(0, 19).replace(/(\d{4})(?=\d)/g, '$1 '),
  vencimiento: (texto) => {
    const digitos = texto.replace(/\D/g, '').slice(0, 4);
    return digitos.length > 2 ? `${digitos.slice(0, 2)}/${digitos.slice(2)}` : digitos;
  },
  cvc: (texto) => texto.replace(/\D/g, '').slice(0, 4),
};

/** Dígito verificador de las tarjetas (algoritmo de Luhn), igual que el servidor. */
function luhnValido(digitos) {
  let total = 0;
  [...digitos].reverse().forEach((c, i) => {
    let n = Number(c);
    if (i % 2 === 1) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    total += n;
  });
  return total % 10 === 0;
}

/**
 * Mismas reglas que validacion.py de suscripciones-flask: el cliente avisa
 * antes de enviar y el servidor vuelve a validar. Devuelve { campo: clave }.
 */
function validar(datos, hoy = new Date()) {
  const errores = {};

  const titular = datos.titular.trim().replace(/\s+/g, ' ');
  if (titular.length < 2 || titular.length > 60) errores.titular = 'plan.form.invalidName';

  const digitos = datos.numero.replace(/[\s-]/g, '');
  if (!/^\d{13,19}$/.test(digitos) || !luhnValido(digitos)) errores.numero = 'plan.form.invalidNumber';

  const partes = VENCIMIENTO.exec(datos.vencimiento.trim());
  const mes = partes ? Number(partes[1]) : 0;
  if (!partes || mes < 1 || mes > 12) {
    errores.vencimiento = 'plan.form.invalidExpiry';
  } else {
    const anio = 2000 + Number(partes[2]);
    // Vale hasta el último día de su mes, como en el servidor.
    if (anio * 12 + mes < hoy.getFullYear() * 12 + hoy.getMonth() + 1) {
      errores.vencimiento = 'plan.form.expired';
    }
  }

  if (!/^\d{3,4}$/.test(datos.cvc.trim())) errores.cvc = 'plan.form.invalidCvc';

  return errores;
}

/**
 * Formulario de pago de Premium (RF-USR-01), con las reglas de T25:
 * validación en el cliente y en el servidor, mensajes traducidos, sin doble
 * envío y sin perder lo escrito si el pago falla.
 *
 * `onPagar(pago)` hace la petición y lanza si falla; `onCancelar` cierra el
 * formulario. La pasarela es simulada: el aviso de arriba lo deja claro y el
 * navegador no ofrece guardar la tarjeta (autoComplete off).
 */
export default function FormularioPago({ titulo, textoBoton, onPagar, onCancelar }) {
  const { t } = useTranslation();
  const [datos, setDatos] = useState(VACIO);
  const [errores, setErrores] = useState({});
  const [errorEnvio, setErrorEnvio] = useState(null);
  const [enviando, setEnviando] = useState(false);
  // Además del estado: bloquea un segundo envío antes de que React vuelva a pintar.
  const enviandoRef = useRef(false);
  const refs = useRef({});

  function cambiar(campo) {
    return (evento) => {
      const formato = FORMATOS[campo];
      const valor = formato ? formato(evento.target.value) : evento.target.value;
      setDatos((d) => ({ ...d, [campo]: valor }));
      // El error de un campo se borra al corregirlo; los demás se mantienen.
      if (errores[campo]) setErrores((e) => ({ ...e, [campo]: undefined }));
    };
  }

  async function enviar(evento) {
    evento.preventDefault();
    if (enviandoRef.current) return;

    const encontrados = validar(datos);
    setErrores(encontrados);
    const primero = CAMPOS.find((c) => encontrados[c]);
    if (primero) {
      refs.current[primero]?.focus();
      return;
    }

    enviandoRef.current = true;
    setEnviando(true);
    setErrorEnvio(null);
    try {
      await onPagar({
        titular: datos.titular.trim(),
        numero: datos.numero.replace(/[\s-]/g, ''),
        vencimiento: datos.vencimiento.trim(),
        cvc: datos.cvc.trim(),
      });
    } catch (e) {
      // El servicio manda `error` ya traducido: tarjeta rechazada (402),
      // pasarela caída (503) o un dato que el servidor no aceptó (400).
      setErrorEnvio(e.message);
    } finally {
      enviandoRef.current = false;
      setEnviando(false);
    }
  }

  function campo(nombre, props) {
    const id = `pago-${nombre}`;
    const error = errores[nombre];
    return (
      <div className="pago-campo">
        <label htmlFor={id}>{t(`plan.form.${nombre}`)}</label>
        <input
          id={id}
          ref={(el) => { refs.current[nombre] = el; }}
          value={datos[nombre]}
          onChange={cambiar(nombre)}
          readOnly={enviando}
          autoComplete="off"
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          {...props}
        />
        {error && <p id={`${id}-error`} className="pago-campo__error">{t(error)}</p>}
      </div>
    );
  }

  return (
    <form className="pago" onSubmit={enviar} noValidate aria-label={titulo}>
      <p className="pago-aviso">{t('plan.form.simulated')}</p>

      {campo('titular', { maxLength: 60 })}
      {campo('numero', { inputMode: 'numeric', maxLength: 23, placeholder: '0000 0000 0000 0000' })}
      <div className="pago-fila">
        {campo('vencimiento', { inputMode: 'numeric', maxLength: 5, placeholder: t('plan.form.expiryPlaceholder') })}
        {campo('cvc', { inputMode: 'numeric', maxLength: 4, placeholder: '123' })}
      </div>

      {errorEnvio && <p className="hm-status hm-status--error" role="alert">{errorEnvio}</p>}
      {enviando && <p className="hm-status hm-status--loading" role="status">{t('plan.form.paying')}</p>}

      <div className="pago-acciones">
        <button type="button" className="plan-enlace" onClick={onCancelar} disabled={enviando}>
          {t('plan.form.back')}
        </button>
        <button type="submit" className="hm-btn hm-btn--jade" disabled={enviando}>
          {textoBoton}
        </button>
      </div>
    </form>
  );
}
