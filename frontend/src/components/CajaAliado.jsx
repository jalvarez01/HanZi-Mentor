import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAsync } from '../hooks/useAsync';
import { abrirCajaAliado, listarCajasAliado } from '../services/api';
import './CajaAliado.css';

/**
 * Sección del equipo aliado en Inicio (T26): abrir una caja de VaultDrop.
 *
 * Los datos pasan por nuestro backend (aliado-flask), que sortea un ítem con
 * las probabilidades que publica VaultDrop. Si VaultDrop no responde, el
 * backend usa su último catálogo (`respaldo`) y aquí se avisa; si nunca
 * respondió, la sección muestra el error con "Reintentar" y el resto de la
 * página sigue igual.
 */
export default function CajaAliado() {
  const { t } = useTranslation();
  const { datos, cargando, error, recargar } = useAsync(listarCajasAliado, []);
  const [cajaId, setCajaId] = useState(null);
  const [premio, setPremio] = useState(null);
  const [abriendo, setAbriendo] = useState(false);
  const [errorAbrir, setErrorAbrir] = useState(null);
  // Cada apertura monta el premio de nuevo: vuelve la animación y la imagen.
  const [tirada, setTirada] = useState(0);
  const abriendoRef = useRef(false);

  const cajas = datos?.cajas ?? [];
  const elegida = cajas.find((c) => c.id === cajaId) ?? cajas[0];

  async function abrir() {
    if (!elegida || abriendoRef.current) return;
    abriendoRef.current = true;
    setAbriendo(true);
    setErrorAbrir(null);
    try {
      setPremio(await abrirCajaAliado(elegida.id));
      setTirada((n) => n + 1);
    } catch (e) {
      setErrorAbrir(e.message);
    } finally {
      abriendoRef.current = false;
      setAbriendo(false);
    }
  }

  const respaldo = premio?.respaldo ?? datos?.respaldo;
  // VaultDrop usa COMUN, RARO, EPICO y LEGENDARIO; otra rareza se muestra tal cual.
  const rareza = premio?.item.rareza.toLowerCase();

  return (
    <section className="home-seccion hm-panel aliado" aria-labelledby="aliado-titulo">
      <div className="hm-section-head">
        <div>
          <span className="hm-kicker">{t('ally.kicker')}</span>
          <h2 id="aliado-titulo">{t('ally.title')}</h2>
        </div>
      </div>

      <p className="aliado-texto">{t('ally.description')}</p>

      {cargando && <p className="hm-status hm-status--loading" role="status">{t('ally.loading')}</p>}

      {error && !datos && (
        <div className="hm-status hm-status--error aliado-error" role="alert">
          <span>{error}</span>
          <button type="button" className="aliado-enlace" onClick={recargar}>{t('common.retry')}</button>
        </div>
      )}

      {datos?.proveedor === 'falso' && <p className="aliado-aviso">{t('ally.sample')}</p>}
      {respaldo && <p className="aliado-aviso">{t('ally.fallback')}</p>}

      {cajas.length > 0 && (
        <>
          {cajas.length > 1 && (
            <div className="aliado-campo">
              <label htmlFor="aliado-caja">{t('ally.box')}</label>
              <select
                id="aliado-caja"
                value={elegida?.id ?? ''}
                onChange={(e) => { setCajaId(Number(e.target.value)); setPremio(null); }}
                disabled={abriendo}
              >
                {cajas.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </select>
            </div>
          )}

          <button type="button" className="hm-btn hm-btn--block" onClick={abrir} disabled={abriendo}>
            {abriendo ? t('ally.opening') : t('ally.open', { caja: elegida?.nombre })}
          </button>

          {errorAbrir && <p className="hm-status hm-status--error aliado-resultado" role="alert">{errorAbrir}</p>}

          <div aria-live="polite">
            {premio && !errorAbrir && (
              <div key={tirada} className={`aliado-premio aliado-premio--${rareza}`}>
                {premio.item.imagen_url && <ImagenPremio src={premio.item.imagen_url} />}
                <div>
                  <p className="aliado-premio__titulo">{t('ally.won')}</p>
                  <p className="aliado-premio__nombre">{premio.item.nombre}</p>
                  <p className="aliado-premio__detalle">
                    {t('ally.detail', {
                      rareza: t(`ally.rarity.${rareza}`, { defaultValue: premio.item.rareza }),
                      valor: premio.item.valor_estimado,
                      probabilidad: premio.item.probabilidad,
                    })}
                  </p>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      <p className="aliado-credito">{t('ally.credit')}</p>
    </section>
  );
}

/**
 * La imagen viene del servidor de VaultDrop: solo se muestra cuando carga.
 * Mientras tanto, o si falla, no ocupa espacio ni deja un ícono roto.
 */
function ImagenPremio({ src }) {
  const [cargada, setCargada] = useState(false);
  return (
    <img
      src={src}
      alt=""
      className="aliado-premio__imagen"
      hidden={!cargada}
      onLoad={() => setCargada(true)}
    />
  );
}
