import TopBar from '../components/TopBar';
import { useAsync } from '../hooks/useAsync';
import { useUsuario } from '../hooks/useUsuario';
import { obtenerProgreso } from '../services/api';
import './Progreso.css';

export default function Progreso() {
  const { usuarioId, reiniciar } = useUsuario();

  const { datos, cargando, error, recargar } = useAsync(
    () => obtenerProgreso(usuarioId),
    [usuarioId],
    Boolean(usuarioId),
  );

  return (
    <>
      <TopBar title="Progreso" />

      <div className="screen-pad progreso">
        {error && <p className="error">{error}</p>}
        {cargando && <p className="cargando">Cargando…</p>}

        {datos && (
          <>
            <div className="tarjetas">
              <Tarjeta
                valor={`${Math.round(datos.tasa_acierto * 100)}%`}
                etiqueta="Tasa de acierto"
                color="var(--jade)"
              />
              <Tarjeta
                valor={datos.total_dominados}
                etiqueta="Dominados"
                color="var(--gold)"
              />
              <Tarjeta
                valor={datos.total_por_reforzar}
                etiqueta="Por reforzar"
                color="var(--seal)"
              />
            </div>

            <section className="bloque">
              <h3>Nivel</h3>
              <div className="niveles-fila">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <span
                    key={n}
                    className={`nivel ${n <= datos.nivel_max_desbloqueado ? 'abierto' : ''}`}
                  >
                    HSK{n}
                  </span>
                ))}
              </div>
              <p className="pie">
                Practicando HSK{datos.nivel_hsk} · desbloqueado hasta HSK
                {datos.nivel_max_desbloqueado}
              </p>
            </section>

            <section className="bloque">
              <h3>Lo que más te cuesta</h3>
              {datos.caracteres_debiles.length === 0 ? (
                <p className="vacio">Todavía no hay errores registrados.</p>
              ) : (
                datos.caracteres_debiles.map((d) => (
                  <div key={d.caracter} className="fila-debil">
                    <span className="hanzi">{d.caracter}</span>
                    <div className="barra">
                      <div
                        className="relleno"
                        style={{ width: `${Math.min(100, d.fallos * 15)}%` }}
                      />
                    </div>
                    <span className="cuenta">{d.fallos}</span>
                  </div>
                ))
              )}
            </section>

            <section className="bloque">
              <h3>Dominados</h3>
              {datos.caracteres_dominados.length === 0 ? (
                <p className="vacio">Ninguno todavía. Acertá un carácter para sumarlo.</p>
              ) : (
                <div className="chips">
                  {datos.caracteres_dominados.map((c) => (
                    <span key={c} className="chip">{c}</span>
                  ))}
                </div>
              )}
            </section>

            <section className="bloque">
              <h3>Próximo repaso</h3>
              <p className="pie">
                {datos.proximo_repaso
                  ? new Date(datos.proximo_repaso).toLocaleString('es-CO', {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })
                  : 'Sin repasos agendados.'}
              </p>
            </section>

            <div className="acciones-pie">
              <button className="btn-secundario" onClick={recargar}>
                Actualizar
              </button>
              <button className="btn-secundario peligro" onClick={reiniciar}>
                Empezar como usuario nuevo
              </button>
            </div>

            <p className="id-usuario">id: {usuarioId}</p>
          </>
        )}
      </div>
    </>
  );
}

function Tarjeta({ valor, etiqueta, color }) {
  return (
    <div className="tarjeta">
      <span className="tarjeta-valor" style={{ color }}>{valor}</span>
      <span className="tarjeta-etiqueta">{etiqueta}</span>
    </div>
  );
}
