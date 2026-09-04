"""
Listas de caracteres por nivel HSK (estándar clásico, 6 niveles).

Un carácter aparece en un único nivel: el nivel en el que el examen oficial
lo introduce por primera vez (equivalente a la variante "exclusive" de la
fuente, no acumulativa). Un carácter que no está en ninguna lista queda sin
clasificar (nivel_hsk NULL en BD) y puede aparecer en lecciones de cualquier
nivel — ver LeccionBuilder.con_caracteres_del_nivel.

Fuente: listas de vocabulario HSK 2.0 (niveles clásicos 1-6) del proyecto
"Complete HSK Vocabulary" — https://github.com/drkameleon/complete-hsk-vocabulary
(wordlists/exclusive/old/1..6.json), filtrando solo entradas de un carácter.
"""

CARACTERES_POR_NIVEL = {
    1: list("一七三上下不个九书买了二五些人他会住你做八六写冷几十去叫吃吗听呢和哪喂喝四回在坐块多大太她好字家小少岁年开很想我日是月有本来水没点热爱狗猫的看能茶菜请读谁这那都里钱零"),
    2: list("两为也从件元再出别到千卖号向吧外姓它完就张得忙快您慢懂找新晴最次每比洗玩白百真着票离穿笑累红给船药要让课贵走路踢近还进远送错长门问阴雪题高鱼黑"),
    3: list("万东久云伞位低使信借像先关冬分刮刷刻包半南又双口只哭啊地坏夏层差带才把拿换接搬放教敢旧春更条极树楼段河渴灯班甜用画疼瘦短矮碗祝秋种站米糖绿老胖脚脸腿花草蓝被西角讲越跟辆难鞋饱饿马骑鸟黄"),
    4: list("与丢之乱交亮亿以份俩修倍假光内刀剩却厚发取台各吵呀咸响嘴困圆场墙够宽寄富对尝帅干底座弄弹当往懒戴扔抬抱拉挂指挺掉推撞擦收敲断无暗朵桥梦棵死汗汤深满火猜猪由留盐省破硬租穷窄笨等算篇群而脏脱苦血行试谈赚赢趟躺软轻输辣过连逛遍酸醒陪页顿香骗"),
    5: list("丁丑丙举乖乘乙伸便倒催傻克册冲冻凭切则劝匹升卷县吐吓吨吹吻呆咬哈唉喊嚷团圈堆塔壶夜夸套娶嫁嫩存官届岛岸布幅平弯弱念恨所扶批抄抢披拆拍拦挡挥捐捡提插搞摆摇摔摘摸撕支救斜方晒晕朝杀枪某根桃梨棒横欠歇正歪毛洒洞派浅浇浓涨淡滚滴漏灰炒烂烫煎煮片牵狼甩甲痒盆盖直睁瞎瞧砍碎秒税类粒系紧紫绕翻肺胃背胸腰臭节薄蛇装诗趁踩蹲退逃递逗醉醋重钓钟铃铜银锁锅闯闻阵除雷雾露青非顶项颗飘骂龙"),
    6: list("丛串丸井亦党兜刺副割劈勿叼吊吼呵咋哄哇哦哨哼啃啥啦嗨嗯嘛嘿坑坡垫塌嫌孔宰屑岔州巷幢弦愈愣憋扁扎扑扒扛折拄拣拧拽拾挎挨挪捎捏捞捧掏掐掰揉揍搀搁搂搓搭攒数晾束枚枝染栋株桨梢橙氢泼涮淋渣溅溜溪烘熨熬犬甭畔番疤瘸皆盛盯眨眯瞪砸磅磕秃秤窜窝竖端筐粥组绣罐翘翼耍耸腥腮膜臂舔舟舱艘茎蒙贼趴跌跨跪蹦蹬迈逢铺锤霞颇馋"),
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
