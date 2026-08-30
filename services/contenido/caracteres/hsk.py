"""
Listas de caracteres por nivel HSK.

Subconjunto reducido para desarrollo. Las listas oficiales completas
(HSK 2.0: 150/300/600/1200/2500/5000 caracteres) se cargan aparte;
esto alcanza para levantar el servicio y correr los tests.
"""

CARACTERES_POR_NIVEL = {
    1: list("一二三四五六七八九十人口日月水火山大小中上下不了是我你他的在有个来去好"),
    2: list("学校老师同朋友书本笔课房间时候早晚吃喝走跑说话看听写读做"),
    3: list("经济政府社会文化历史科技研究发展环境问题方法结果影响"),
    4: list("资源技术管理组织制度政策计划目标实现提高改善解决"),
    5: list("哲理逻辑概念思维观点态度价值意义精神物质意识存在"),
    6: list("宪司权利义务法律条款规定执行审判判决辩护证据"),
}


def nivel_de(hanzi):
    """Devuelve el nivel HSK de un carácter, o None si no está en las listas."""
    for nivel, caracteres in CARACTERES_POR_NIVEL.items():
        if hanzi in caracteres:
            return nivel
    return None


def caracteres_hasta(nivel):
    """Todos los caracteres desde HSK 1 hasta el nivel indicado."""
    acumulado = []
    for n in range(1, nivel + 1):
        acumulado.extend(CARACTERES_POR_NIVEL.get(n, []))
    return acumulado
