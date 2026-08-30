"""
Agente tutor con LangGraph.

Grafo de tres nodos:

    analizar → decidir_dificultad → seleccionar_caracteres

`analizar` resume el estado del estudiante sin llamar al modelo (barato y
determinista). Los otros dos sí consultan al LLM, cada uno con una tarea
acotada y una salida en JSON que se valida antes de devolverla.

Si el LLM falla o responde algo que no se puede parsear, cada nodo cae a
una heurística local. El agente nunca deja al usuario sin sesión.
"""

import json
import os
from typing import TypedDict

UMBRAL_DIFICULTAD_ALTA = 0.85
UMBRAL_DIFICULTAD_MEDIA = 0.6


class EstadoTutor(TypedDict, total=False):
    """Lo que viaja entre nodos del grafo."""

    tarea: str
    progreso: dict
    cantidad: int
    resumen: str
    dificultad: int
    caracteres: list


# --------------------------------------------------------------------------
# Nodos
# --------------------------------------------------------------------------


def nodo_analizar(estado: EstadoTutor) -> EstadoTutor:
    """Traduce el progreso crudo a una descripción que el modelo entienda."""
    progreso = estado.get("progreso", {})

    dominados = progreso.get("caracteres_dominados", [])
    errores = progreso.get("errores_frecuentes", {})
    tasa = progreso.get("tasa_acierto", 0.5)
    nivel = progreso.get("nivel_hsk", 1)

    peores = sorted(errores.items(), key=lambda par: par[1], reverse=True)[:5]
    detalle_errores = ", ".join(f"{c} ({n} fallos)" for c, n in peores) or "ninguno"

    estado["resumen"] = (
        f"Estudiante de nivel HSK{nivel}. "
        f"Tasa de acierto: {tasa:.0%}. "
        f"Domina {len(dominados)} caracteres. "
        f"Caracteres problemáticos: {detalle_errores}."
    )
    return estado


def nodo_decidir_dificultad(estado: EstadoTutor) -> EstadoTutor:
    """Pide al modelo un entero de 1 a 5; si falla, usa la heurística."""
    prompt = (
        f"{estado['resumen']}\n\n"
        "Elegí la dificultad para su próxima sesión de práctica, de 1 (muy fácil) "
        "a 5 (muy difícil). Considerá que una dificultad demasiado alta desmotiva "
        "y una demasiado baja aburre.\n"
        'Respondé SOLO con JSON: {"dificultad": <entero 1-5>}'
    )

    respuesta = _consultar_modelo(prompt)

    try:
        valor = int(respuesta["dificultad"])
        estado["dificultad"] = max(1, min(5, valor))
    except (TypeError, KeyError, ValueError):
        estado["dificultad"] = _dificultad_heuristica(estado.get("progreso", {}))

    return estado


def nodo_seleccionar_caracteres(estado: EstadoTutor) -> EstadoTutor:
    """Pide al modelo qué caracteres nuevos enseñar, filtrando los ya dominados."""
    progreso = estado.get("progreso", {})
    cantidad = estado.get("cantidad", 4)
    dominados = set(progreso.get("caracteres_dominados", []))
    nivel = progreso.get("nivel_hsk", 1)

    prompt = (
        f"{estado['resumen']}\n\n"
        f"Proponé {cantidad} caracteres chinos simplificados de nivel HSK{nivel} "
        f"para que aprenda a continuación. No incluyas ninguno de estos, que ya "
        f"domina: {', '.join(sorted(dominados)) or 'ninguno'}.\n"
        "Preferí caracteres frecuentes y con componentes que ya haya visto.\n"
        'Respondé SOLO con JSON: {"caracteres": ["字", "字", ...]}'
    )

    respuesta = _consultar_modelo(prompt)

    propuestos = respuesta.get("caracteres") if isinstance(respuesta, dict) else None

    if not isinstance(propuestos, list) or not propuestos:
        propuestos = _caracteres_heuristicos(nivel, dominados, cantidad)

    limpios = [
        c for c in propuestos
        if isinstance(c, str) and len(c) == 1 and c not in dominados
    ]

    if len(limpios) < cantidad:
        respaldo = _caracteres_heuristicos(nivel, dominados | set(limpios), cantidad)
        limpios.extend(respaldo)

    estado["caracteres"] = limpios[:cantidad]
    return estado


# --------------------------------------------------------------------------
# Llamada al modelo
# --------------------------------------------------------------------------


def _consultar_modelo(prompt: str) -> dict:
    """
    Envía el prompt al LLM y parsea su respuesta como JSON.

    Devuelve un dict vacío ante cualquier problema: falta de credenciales,
    error de red o respuesta no parseable. Los nodos ya manejan ese caso.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {}

    try:
        import anthropic

        cliente = anthropic.Anthropic(api_key=api_key)
        mensaje = cliente.messages.create(
            model=os.getenv("TUTOR_MODEL", "claude-sonnet-4-6"),
            max_tokens=512,
            system=(
                "Sos un tutor de chino mandarín. Respondés únicamente con JSON "
                "válido, sin explicaciones, sin markdown, sin bloques de código."
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        texto = "".join(
            bloque.text for bloque in mensaje.content if bloque.type == "text"
        ).strip()

        texto = texto.removeprefix("```json").removeprefix("```").removesuffix("```")
        return json.loads(texto.strip())

    except Exception:
        # Cualquier fallo cae a la heurística del nodo. No rompemos la sesión.
        return {}


# --------------------------------------------------------------------------
# Heurísticas de respaldo
# --------------------------------------------------------------------------

CATALOGO_POR_NIVEL = {
    1: ["人", "口", "日", "月", "水", "火", "山", "大", "小", "中"],
    2: ["学", "校", "老", "师", "同", "朋", "友", "书", "本", "笔"],
    3: ["经", "济", "政", "府", "社", "会", "文", "化", "历", "史"],
    4: ["环", "境", "资", "源", "技", "术", "发", "展", "研", "究"],
    5: ["哲", "学", "逻", "辑", "概", "念", "理", "论", "思", "维"],
    6: ["宪", "法", "司", "立", "权", "利", "义", "务", "制", "度"],
}


def _dificultad_heuristica(progreso: dict) -> int:
    tasa = progreso.get("tasa_acierto", 0.5)
    if tasa >= UMBRAL_DIFICULTAD_ALTA:
        return 4
    if tasa >= UMBRAL_DIFICULTAD_MEDIA:
        return 3
    return 2


def _caracteres_heuristicos(nivel: int, dominados: set, cantidad: int) -> list:
    catalogo = CATALOGO_POR_NIVEL.get(nivel, CATALOGO_POR_NIVEL[1])
    return [c for c in catalogo if c not in dominados][:cantidad]


# --------------------------------------------------------------------------
# Construcción del grafo
# --------------------------------------------------------------------------


def construir_agente():
    """
    Devuelve el grafo compilado, con `.invoke(estado)`.

    Si LangGraph no está instalado, devuelve un sustituto que ejecuta los
    mismos nodos en secuencia. Así el servicio arranca igual y el código
    que lo consume no cambia.
    """
    try:
        from langgraph.graph import END, START, StateGraph

        grafo = StateGraph(EstadoTutor)

        grafo.add_node("analizar", nodo_analizar)
        grafo.add_node("decidir_dificultad", nodo_decidir_dificultad)
        grafo.add_node("seleccionar_caracteres", nodo_seleccionar_caracteres)

        grafo.add_edge(START, "analizar")
        grafo.add_conditional_edges(
            "analizar",
            _enrutar_por_tarea,
            {
                "dificultad": "decidir_dificultad",
                "caracteres": "seleccionar_caracteres",
            },
        )
        grafo.add_edge("decidir_dificultad", END)
        grafo.add_edge("seleccionar_caracteres", END)

        return grafo.compile()

    except ImportError:
        return AgenteSecuencial()


def _enrutar_por_tarea(estado: EstadoTutor) -> str:
    """El motor pide una cosa a la vez; no hace falta correr todo el grafo."""
    if estado.get("tarea") == "sugerir_dificultad":
        return "dificultad"
    return "caracteres"


class AgenteSecuencial:
    """Mismo comportamiento que el grafo, sin la dependencia de LangGraph."""

    def invoke(self, estado: EstadoTutor) -> EstadoTutor:
        estado = nodo_analizar(dict(estado))

        if estado.get("tarea") == "sugerir_dificultad":
            return nodo_decidir_dificultad(estado)

        return nodo_seleccionar_caracteres(estado)
