import './CuadriculaHanzi.css';

/**
 * Cruz punteada de borde a borde y el carácter centrado en el cruce, como en
 * un cuaderno de caligrafía. Va dentro de una tarjeta que lleva la clase
 * .cuadricula-hanzi (papel y borde); el resto del contenido de la tarjeta
 * (kicker arriba, dato abajo) queda por encima de la cruz.
 *
 * Sin el papel, un carácter de un solo trazo como 一 sobre el paisaje se lee
 * como un guion o una flecha.
 */
export default function CuadriculaHanzi({ hanzi }) {
  return (
    <>
      <div className="cuadricula-hanzi__guias" aria-hidden="true">
        <svg>
          <line x1="50%" y1="0" x2="50%" y2="100%" />
          <line x1="0" y1="50%" x2="100%" y2="50%" />
        </svg>
      </div>
      <span className="cuadricula-hanzi__caracter" lang="zh-Hans">{hanzi}</span>
    </>
  );
}
