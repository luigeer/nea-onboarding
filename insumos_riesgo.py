# -*- coding: utf-8 -*-
"""
insumos_riesgo.py — De Supabase a los cuatro módulos del modelo
================================================================
`modelo_riesgo.evaluar()` recibe cuatro diccionarios y no sabe de dónde salen.
Este módulo los arma leyendo `buro`, `estados_cuenta`, `info_fiscal` y el
expediente. Es la única pieza que traduce nombres de columna a nombres de
variable del modelo, y por eso el único lugar donde hay que tocar si mañana
cambia el esquema.

Tres decisiones que valen más que el código:

**El buró que entra al modelo es el del acreditado, no el del garante.** Son
consultas distintas y ambas se guardan, pero mezclarlas maquilla al cliente: si
el acreditado no tiene historial y su obligado solidario tiene un score de 192,
promediar los dos produce un número que no describe a nadie. El buró del
garante existe para el resumen ejecutivo y para el dictamen de la garantía.

**Se prefieren las cifras operativas.** El analizador de estados de cuenta
reconcilia depósitos y retiros contra los movimientos y publica dos juegos de
números: el declarado en la carátula y el reconstruido. Cuando el reconstruido
existe, gana.

**Un ejercicio fiscal en blanco no es el ejercicio a usar.** Se toma el más
reciente que traiga algo. Si los tres están vacíos —que es exactamente el caso
de una empresa que nunca operó— el módulo se reporta ausente y el modelo
renormaliza, en vez de calificarla con ceros.
"""

from datetime import date

# Cómo se llama cada cifra en `estados_cuenta` y cómo la pide el modelo.
#
# Las columnas `_operativo` traen lo reconciliado contra los movimientos,
# descontando traspasos entre cuentas propias y depósitos de partes
# relacionadas. Para los MONTOS eso es lo que se quiere: mide negocio real.
#
# Para los CONTEOS no. El modelo usa `num_depositos` y `num_retiros` en una
# sola variable —"número promedio de movimientos"— que mide qué tan viva está
# la cuenta. La Llosa recibió 2 depósitos en mayo y 4 en junio; que los seis
# vinieran de su obligado solidario los deja en cero operativo, y pasárselos
# así al modelo diría que la cuenta está inactiva, que es falso. La cuenta se
# mueve; de quién viene el dinero es un hallazgo del resumen ejecutivo, no una
# corrección al conteo.
CAMPOS_PERIODO = {
    "num_depositos":  ("numero_depositos",),
    "num_retiros":    ("numero_retiros",),
    "monto_depositos": ("monto_depositos_operativo", "monto_depositos"),
    "monto_retiros":  ("monto_retiros_operativo", "monto_retiros"),
    "saldo_inicial":  ("saldo_inicial",),
    "saldo_final":    ("saldo_final",),
    "saldo_promedio": ("saldo_promedio",),
    "saldo_min":      ("saldo_minimo",),
    "saldo_max":      ("saldo_maximo",),
}

CAMPOS_BURO = ("ocurrencias_mora", "peor_edo_6m", "consultas_12m", "avales",
               "creditos_abiertos", "creditos_abiertos_ultimo_ano",
               "saldo_actual", "saldo_vencido", "prevenciones", "previsor",
               "score_pyme")

CAMPOS_FISCAL = ("ingresos_totales", "utilidad_operacion", "activo_corto_plazo",
                 "pasivo_corto_plazo", "capital_contable", "inventarios",
                 "dias_para_cobrar", "dias_para_pagar", "dictaminados")


def _fecha(v):
    if isinstance(v, date) or v is None:
        return v
    try:
        return date(*(int(x) for x in str(v)[:10].split("-")))
    except (ValueError, TypeError):
        return None


def _primero(fila, columnas):
    for c in columnas:
        v = fila.get(c)
        if v is not None:
            return v
    return None


# ─────────────────────────────────────────────────────────────────────────────
def perfil(exp):
    """El perfil de empresa más el monto solicitado.

    El monto sale del expediente y no del perfil capturado: dos de los cuatro
    módulos lo dividen entre algo, así que si falta, el modelo entero deja de
    significar. Los cuatro campos del perfil sí pueden faltar —el modelo los
    trata como ausentes, no como malos—.
    """
    from schema_expediente import _get

    p = dict(_get(exp, "perfil_empresa", {}) or {})
    p["monto_solicitado"] = _get(exp, "credito.solicitada.linea")
    p["fecha_constitucion"] = _fecha(
        p.get("fecha_constitucion")
        or _get(exp, "cliente.validado.fecha_constitucion"))
    return p


def buro(folio, sujeto=None, sb=None):
    """El buró del acreditado. `sujeto=None` toma el que no sea del garante."""
    import db
    sb = sb or db.cliente()
    filas = sb.table("buro").select("*").eq("folio", folio) \
              .order("fecha_consulta", desc=True).execute().data or []
    if sujeto:
        filas = [f for f in filas if (f.get("sujeto") or "") == sujeto]
    else:
        filas = [f for f in filas
                 if "obligado solidario" not in (f.get("sujeto") or "").lower()]
    if not filas:
        return {}

    f = filas[0]
    salida = {c: f.get(c) for c in CAMPOS_BURO}
    # "Sin historial" no es lo mismo que "no consultamos": la consulta se hizo
    # y el buró no tiene nada sobre esta empresa. El modelo lee cada variable
    # como ausente, que es la lectura correcta —no hay mora porque no hay
    # crédito—, y el resumen ejecutivo se encarga de decir que eso, en una
    # empresa que pide línea, es en sí mismo una señal.
    salida["resultado"] = f.get("resultado")
    salida["folio_consulta"] = f.get("folio_consulta")
    return salida


def cuentas(folio, sb=None):
    """Las cuentas del cliente, cada una con sus periodos del más reciente al
    más antiguo, que es el orden que el modelo asume."""
    import db
    sb = sb or db.cliente()
    filas = sb.table("estados_cuenta").select("*").eq("folio", folio).execute().data or []

    agrupadas = {}
    for f in filas:
        clave = (f.get("banco"), f.get("cuenta"))
        periodo = {destino: _primero(f, cols)
                   for destino, cols in CAMPOS_PERIODO.items()}
        periodo["_corte"] = str(f.get("fecha_final") or "")
        agrupadas.setdefault(clave, []).append(periodo)

    return [sorted(ps, key=lambda p: p["_corte"], reverse=True)
            for ps in agrupadas.values()]


def declaracion(folio, sb=None):
    """El ejercicio fiscal más reciente que traiga algo.

    Devuelve (fila, ejercicio). Si los tres vienen en blanco devuelve ({}, None)
    y el modelo reporta el módulo ausente: una declaración vacía dice que la
    empresa no operó, no que operó mal.
    """
    import db
    sb = sb or db.cliente()
    filas = sb.table("info_fiscal").select("*").eq("folio", folio) \
              .order("ejercicio", desc=True).execute().data or []
    for f in filas:
        if any(f.get(c) not in (None, 0) for c in CAMPOS_FISCAL):
            return {c: f.get(c) for c in CAMPOS_FISCAL}, f.get("ejercicio")
    return {}, None


# ─────────────────────────────────────────────────────────────────────────────
def reunir(folio, sb=None):
    """Los cuatro insumos más la procedencia de cada uno.

    La procedencia importa: un score construido sobre un ejercicio de 2023 y
    dos estados de cuenta no es el mismo score que uno con 2025 y seis, aunque
    el número salga igual.
    """
    import db
    sb = sb or db.cliente()
    exp = sb.table("expedientes").select("datos").eq("folio", folio).execute().data
    if not exp:
        raise ValueError("No existe el expediente %s" % folio)
    exp = exp[0]["datos"]

    d, ejercicio = declaracion(folio, sb)
    cs = cuentas(folio, sb)
    b = buro(folio, sb=sb)

    return {
        "expediente": exp,
        "perfil": perfil(exp),
        "buro": b,
        "declaracion": d,
        "cuentas": cs,
        "procedencia": {
            "ejercicio_fiscal": ejercicio,
            "periodos_bancarios": sum(len(c) for c in cs),
            "cuentas_bancarias": len(cs),
            "buro": b.get("folio_consulta"),
            "buro_resultado": b.get("resultado"),
        },
    }
