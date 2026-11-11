import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import FormularioPago from './FormularioPago';
import { useSuscripcion } from '../hooks/useSuscripcion';
import { useFormato } from '../i18n/formato';
import { activarPremium, cancelarPremium, obtenerPlanes, renovarPremium } from '../services/api';
import './PlanSuscripcion.css';

/**
 * Panel "Tu plan" en Progreso (RF-USR-01): muestra el plan que rige y deja
 * activar, renovar o cancelar Premium. Lo que se puede hacer lo decide
 * suscripciones-flask en `acciones`; el panel solo muestra esos botones.
 *
 * Practicar enlaza acá (/progreso#plan) desde los niveles HSK 4 a 6.
 */
export default function PlanSuscripcion({ usuarioId }) {
  const { t } = useTranslation();
  const formato = useFormato();
  const { hash } = useLocation();
  const { suscripcion, setSuscripcion, cargando, error, recargar } = useSuscripcion(usuarioId);
  const [premium, setPremium] = useState(null);
  const [formulario, setFormulario] = useState(null); // 'activar' | 'renovar' | null
  const [confirmando, setConfirmando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [errorAccion, setErrorAccion] = useState(null);
  const [exito, setExito] = useState(null);
  const panelRef = useRef(null);
  const tituloRef = useRef(null);

  // El precio sale del servicio, no del frontend. Sin él, el botón va sin precio.
  useEffect(() => {
    obtenerPlanes()
      .then((r) => setPremium(r.planes.find((p) => p.codigo === 'premium') ?? null))
      .catch(() => {});
  }, []);

  // Desde Practicar se llega con #plan: se baja hasta el panel cuando ya cargó.
  useEffect(() => {
    if (hash !== '#plan' || !suscripcion) return;
    const reducir = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    panelRef.current?.scrollIntoView({ behavior: reducir ? 'auto' : 'smooth', block: 'start' });
  }, [hash, suscripcion]);

  function terminar(resultado, clave) {
    setSuscripcion(resultado.suscripcion);
    setFormulario(null);
    setConfirmando(false);
    setExito(t(clave, {
      fecha: formato.fecha(resultado.suscripcion.vence_en),
      referencia: resultado.pago?.referencia,
    }));
    // El foco vuelve al título para que el lector de pantalla lea el nuevo estado.
    tituloRef.current?.focus();
  }

  async function pagar(pago) {
    if (formulario === 'activar') {
      terminar(await activarPremium(usuarioId, pago), 'plan.activated');
    } else {
      terminar(await renovarPremium(usuarioId, pago), 'plan.renewed');
    }
  }

  async function cancelar() {
    if (cancelando) return;
    setCancelando(true);
    setErrorAccion(null);
    try {
      terminar(await cancelarPremium(usuarioId), 'plan.cancelled');
    } catch (e) {
      setErrorAccion(e.message);
    } finally {
      setCancelando(false);
    }
  }

  function abrir(modo) {
    setFormulario(modo);
    setExito(null);
    setErrorAccion(null);
    setConfirmando(false);
  }

  const precio = premium ? formato.dinero(premium.precio, premium.moneda) : null;
  const acciones = suscripcion?.acciones ?? [];

  return (
    <section ref={panelRef} id="plan" className="hm-panel plan" aria-labelledby="plan-titulo">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('plan.kicker')}</span>
          <h2 id="plan-titulo" ref={tituloRef} tabIndex={-1}>{t('plan.title')}</h2>
        </div>
      </div>

      {cargando && <p className="hm-status hm-status--loading" role="status">{t('plan.loading')}</p>}

      {error && !suscripcion && (
        <div className="hm-status hm-status--error plan-error" role="alert">
          <span>{t('plan.error')}</span>
          <button type="button" className="plan-enlace" onClick={recargar}>{t('common.retry')}</button>
        </div>
      )}

      {suscripcion && (
        <>
          <p className="plan-actual">
            {/* Del frontend y no `nombre_plan`: así cambia en cuanto se cambia el idioma */}
            <span className={`plan-insignia plan-insignia--${suscripcion.plan}`}>{t(`plan.name.${suscripcion.plan}`)}</span>
            <span className="plan-niveles">{t('plan.levels', { maximo: suscripcion.nivel_maximo })}</span>
          </p>
          <p className="plan-texto">
            {t(`plan.state.${suscripcion.plan}.${suscripcion.estado}`, {
              fecha: suscripcion.vence_en ? formato.fecha(suscripcion.vence_en) : '',
            })}
          </p>

          {exito && <p className="plan-exito" role="status">{exito}</p>}
          {errorAccion && <p className="hm-status hm-status--error" role="alert">{errorAccion}</p>}

          {formulario ? (
            <FormularioPago
              titulo={t(formulario === 'activar' ? 'plan.activate' : 'plan.renew')}
              textoBoton={precio ? t('plan.form.payAmount', { precio }) : t('plan.form.pay')}
              onPagar={pagar}
              onCancelar={() => setFormulario(null)}
            />
          ) : (
            <div className="plan-acciones">
              {acciones.includes('activar') && (
                <button type="button" className="hm-btn hm-btn--jade" onClick={() => abrir('activar')}>
                  {precio ? t('plan.activateWithPrice', { precio }) : t('plan.activate')}
                </button>
              )}
              {acciones.includes('renovar') && (
                <button type="button" className="hm-btn" onClick={() => abrir('renovar')}>
                  {precio ? t('plan.renewWithPrice', { precio }) : t('plan.renew')}
                </button>
              )}
              {acciones.includes('cancelar') && !confirmando && (
                <button type="button" className="plan-enlace" onClick={() => setConfirmando(true)}>
                  {t('plan.cancel')}
                </button>
              )}
            </div>
          )}

          {confirmando && !formulario && (
            <div className="plan-confirmar" role="group" aria-labelledby="plan-confirmar-texto">
              <p id="plan-confirmar-texto">
                {t('plan.cancelConfirm', { fecha: formato.fecha(suscripcion.vence_en) })}
              </p>
              <div className="plan-acciones">
                <button type="button" className="hm-btn" onClick={cancelar} disabled={cancelando}>
                  {t('plan.cancelYes')}
                </button>
                <button type="button" className="plan-enlace" onClick={() => setConfirmando(false)} disabled={cancelando}>
                  {t('plan.cancelNo')}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
