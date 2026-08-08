# -*- coding: utf-8 -*-
"""
info_fiscal.py — De la declaración anual de Syntage al modelo de riesgo
========================================================================
Syntage devuelve la declaración anual como el SAT la estructura: un árbol
hondo de conceptos, cada uno con `Total`, `Notas` y a veces el desglose entre
partes relacionadas y no relacionadas. El modelo consume siete cifras.

Este módulo hace esa traducción, y de paso rescata dos datos que el modelo no
mira pero que la especificación pide para el resumen ejecutivo: los ingresos
con partes relacionadas —la facturación intercompañía— y los intereses
moratorios.

`syntage_datos` guarda el árbol completo; `info_fiscal` es esta proyección. Si
mañana el modelo necesita otro concepto, se relee de lo guardado sin volver a
extraer.
"""

# Dónde vive cada cifra dentro del árbol. La primera ruta que exista gana: los
# nombres cambian según el régimen y según si el ejercicio dio utilidad o
# pérdida.
ESTADO_RESULTADOS = "ESTADO DE RESULTADOS"
BALANCE = "ESTADO DE POSICIÓN FINANCIERA (BALANCE)"

CONCEPTOS = {
    "ingresos_totales":   [("Ingresos Netos",)],
    "utilidad_operacion": [("Utilidad de operación",), ("Pérdida de operación",)],
    "utilidad_neta":      [("Utilidad neta",), ("Pérdida neta",)],
    "costo_ventas":       [("Costo de ventas",), ("Costo de servicios",)],
    "gastos_operacion":   [("Gastos de operación",)],
}

# Los conceptos de pérdida vienen en positivo en la declaración: hay que
# invertirles el signo para que el modelo los lea como lo que son.
NEGATIVOS = {"Pérdida de operación", "Pérdida neta", "Pérdida Bruta",
             "Pérdida antes de Impuestos a la utilidad",
             "Pérdida de operaciones continuas"}


def _total(nodo):
    """Saca el Total de un nodo del árbol, sin importar cuán hondo esté."""
    if nodo is None:
        return None
    if isinstance(nodo, (int, float)):
        return float(nodo)
    if isinstance(nodo, dict):
        t = nodo.get("Total")
        return float(t) if isinstance(t, (int, float)) else None
    return None


def _buscar(arbol, camino):
    cur = arbol
    for paso in camino:
        if not isinstance(cur, dict) or paso not in cur:
            return None
        cur = cur[paso]
    return cur


def _primero(arbol, caminos):
    """Devuelve (valor, concepto) del primer camino con dato."""
    for camino in caminos:
        v = _total(_buscar(arbol, camino))
        if v is not None:
            concepto = camino[-1]
            return (-v if concepto in NEGATIVOS else v), concepto
    return None, None


def _hondo(nodo, etiqueta, profundidad=6):
    """Suma todos los `Total` de las ramas cuyo nombre contenga la etiqueta.

    El SAT reparte un mismo concepto entre varios renglones —hay ocho lugares
    donde puede aparecer un interés moratorio—, así que hay que recorrer.
    """
    if profundidad < 0 or not isinstance(nodo, dict):
        return None
    total = None
    for clave, hijo in nodo.items():
        if etiqueta.lower() in clave.lower():
            v = _total(hijo)
            if v is not None:
                total = (total or 0) + v
        sub = _hondo(hijo, etiqueta, profundidad - 1)
        if sub is not None:
            total = (total or 0) + sub
    return total


def _partes_relacionadas(nodo, profundidad=6):
    """Suma lo facturado a partes relacionadas donde sea que aparezca."""
    if profundidad < 0 or not isinstance(nodo, dict):
        return None
    total = None
    for clave, hijo in nodo.items():
        if clave == "Partes Relacionadas" and isinstance(hijo, (int, float)):
            total = (total or 0) + float(hijo)
        elif isinstance(hijo, dict):
            sub = _partes_relacionadas(hijo, profundidad - 1)
            if sub is not None:
                total = (total or 0) + sub
    return total


def desde_declaracion(datos, ejercicio, fuente="syntage"):
    """Traduce el árbol de una declaración anual a la fila de `info_fiscal`.

    Devuelve (fila, procedencia). La procedencia dice de qué concepto exacto
    salió cada cifra, porque 'Utilidad de operación' y 'Pérdida de operación'
    son renglones distintos y conviene saber cuál se usó.
    """
    er = datos.get(ESTADO_RESULTADOS) or {}
    bal = datos.get(BALANCE) or {}
    procedencia = {}
    fila = {"ejercicio": ejercicio, "fuente": fuente}

    for campo, caminos in CONCEPTOS.items():
        valor, concepto = _primero(er, caminos)
        if campo in ("ingresos_totales", "utilidad_operacion"):
            fila[campo] = valor
        if concepto:
            procedencia[campo] = concepto

    # El total de cada grupo del balance no cuelga del grupo: vive un nivel
    # más abajo, en un renglón que repite el nombre. Se prueban las dos rutas.
    def del_balance(*rutas):
        for r in rutas:
            v = _total(_buscar(bal, r))
            if v is not None:
                return v
        return None

    fila["activo_corto_plazo"] = del_balance(
        ("ACTIVO", "ACTIVO A CORTO PLAZO", "Total de Activo a corto plazo"),
        ("ACTIVO", "ACTIVO A CORTO PLAZO"))
    fila["pasivo_corto_plazo"] = del_balance(
        ("PASIVO", "PASIVO A CORTO PLAZO", "Total de Pasivo a corto plazo"),
        ("PASIVO", "PASIVO A CORTO PLAZO"))
    fila["capital_contable"] = del_balance(
        ("CAPITAL", "TOTAL DE CAPITAL CONTABLE"),
        ("CAPITAL", "CAPITAL CONTABLE"))
    fila["inventarios"] = _hondo(_buscar(bal, ("ACTIVO",)) or {}, "Inventario")

    # El modelo no las mira; el resumen ejecutivo sí debe.
    fila["ingresos_partes_relacionadas"] = _partes_relacionadas(er)

    # `dictaminados` no viene en la declaración: se captura aparte.
    fila["dictaminados"] = None
    return fila, procedencia


# ─────────────────────────────────────────────────────────────────────────────
# Proyección desde los insights `metrics/*`
# ─────────────────────────────────────────────────────────────────────────────
# Los endpoints `metrics/balance-sheet` y `metrics/income-statement` no
# devuelven un ejercicio: devuelven cinco. Cada nodo es
#
#     {"category": "Activo a corto plazo",
#      "2022": {"Total": null}, "2023": {"Total": 100000.0}, ...,
#      "children": [...]}
#
# y el árbol cubre años que todavía no se declaran. Un `null` ahí no significa
# lo mismo en todos los años, y confundirlo cambia el score:
#
#   ejercicio NO declarado    todos sus nodos vienen en null. No sabemos nada;
#                             la fila no se escribe y el módulo queda ausente.
#   ejercicio SÍ declarado    el SAT rellena con 0.0 las líneas que calcula y
#                             deja en null las que el contribuyente no llenó.
#                             Ahí un null es un cero declarado.
#
# La distinción no contradice el principio de que la ausencia de un dato no es
# un dato desfavorable: ese principio habla de datos que a NOSOTROS nos faltan.
# Una declaración presentada con utilidad bruta cero y el renglón de ingresos
# en blanco no es información faltante — es una empresa que declaró no haber
# vendido. Leerlo como "no sé" saca la variable del promedio y sube el score de
# una empresa que no facturó.
BALANCE_INSIGHT = {
    "activo_corto_plazo": ("Activo", "Activo a corto plazo"),
    "pasivo_corto_plazo": ("Pasivo", "Pasivo a corto plazo"),
    "capital_contable":   ("Capital", "Capital contable"),
}

RESULTADOS_INSIGHT = {
    "ingresos_totales":   ("Ingresos Netos",),
    "utilidad_operacion": ("Utilidad de operación", "Pérdida de operación"),
}


def _nodos(payload):
    """Aplana el árbol de un insight a {categoría: nodo}, el primero que gane.

    Las categorías se repiten entre niveles —"Utilidad de operación" cuelga de
    sí misma— y el de arriba es el bueno.
    """
    fuera = {}

    def bajar(nodos):
        for n in nodos or []:
            if isinstance(n, dict):
                fuera.setdefault(n.get("category"), n)
                bajar(n.get("children"))

    bajar((payload or {}).get("data"))
    return fuera


def _anio(nodo, ejercicio):
    v = (nodo or {}).get(str(ejercicio))
    v = v.get("Total") if isinstance(v, dict) else v
    return float(v) if isinstance(v, (int, float)) else None


def ejercicios_declarados(*payloads):
    """Qué años tienen declaración presentada, según los propios árboles.

    Un año declarado deja rastro: alguno de sus nodos trae un número, aunque
    sea cero. Un año sin declarar viene entero en null.
    """
    anios = set()
    for p in payloads:
        for nodo in _nodos(p).values():
            for clave in nodo:
                if clave.isdigit() and _anio(nodo, clave) is not None:
                    anios.add(int(clave))
    return sorted(anios)


def desde_insights(balance, resultados, fuente="syntage"):
    """Una fila de `info_fiscal` por ejercicio declarado.

    Devuelve la lista de filas. Los años sin declaración no producen fila: no
    hay nada que proyectar y una fila de ceros mentiría.
    """
    nb, nr = _nodos(balance), _nodos(resultados)
    filas = []

    for ejercicio in ejercicios_declarados(balance, resultados):
        fila = {"ejercicio": ejercicio, "fuente": fuente, "declarado": True}

        for campo, categorias in BALANCE_INSIGHT.items():
            fila[campo] = next(
                (_anio(nb.get(c), ejercicio) for c in categorias
                 if _anio(nb.get(c), ejercicio) is not None), 0.0)

        for campo, categorias in RESULTADOS_INSIGHT.items():
            valor, concepto = None, None
            for c in categorias:
                v = _anio(nr.get(c), ejercicio)
                if v is not None:
                    valor, concepto = v, c
                    break
            # En un ejercicio declarado, el renglón en blanco es un cero.
            if valor is None:
                valor = 0.0
            elif concepto in NEGATIVOS:
                valor = -valor
            fila[campo] = valor

        inv = [n for cat, n in nb.items() if cat and "inventario" in cat.lower()]
        vals = [_anio(n, ejercicio) for n in inv]
        vals = [v for v in vals if v is not None]
        fila["inventarios"] = sum(vals) if vals else 0.0

        fila["dictaminados"] = None
        filas.append(fila)

    return filas


def a_supabase(folio, filas, sb=None):
    """Guarda las filas en `info_fiscal`, una por ejercicio."""
    import db
    sb = sb or db.cliente()
    guardadas = 0
    for f in filas:
        fila = dict(f, folio=folio, obtenido=None)
        fila.pop("obtenido")
        sb.table("info_fiscal").upsert(
            fila, on_conflict="folio,ejercicio,fuente").execute()
        guardadas += 1
    return guardadas
