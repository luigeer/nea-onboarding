# -*- coding: utf-8 -*-
"""
modelo_riesgo.py — El modelo de riesgo de Nea, en código
=========================================================
Transcripción fiel del modelo en Excel, con los defectos corregidos. Sirve
para dos cosas: calcular el score desde el expediente sin abrir Excel, y
demostrar qué cambia cada corrección — `evaluar(..., legado=True)` reproduce
el comportamiento viejo, celda por celda.

Cuatro módulos ponderados:
    estados de cuenta 27.5% · declaración anual 27.5% · buró 25% · perfil 20%
    score >= 0.70 aprueba · >= 0.50 va a comité · abajo se rechaza

Principio que ordena las correcciones: **la ausencia de un dato no es un dato
desfavorable.** Un cliente sin créditos abiertos no es un mal cliente, es un
cliente del que no se sabe. Para un emisor que coloca flotillas en PyMEs con
expediente delgado, confundir las dos cosas sesga en contra justo de los
clientes que se quieren.

Cuando falta un dato, la variable devuelve None, se cae del promedio y las
ponderaciones del módulo se renormalizan sobre lo que sí hay. Si a un módulo
no le queda ninguna variable, el módulo entero se cae y los otros tres se
renormalizan entre ellos.
"""

from datetime import date

# ─────────────────────────────────────────────────────────────────────────────
PESOS_MODULO = {
    "edos_cuenta": 0.275,
    "declaracion_anual": 0.275,
    "buro": 0.25,
    "perfil_empresa": 0.20,
}

UMBRAL_APROBADO = 0.70
UMBRAL_COMITE = 0.50
FACTOR_AMPLIACION = 1.2      # arriba de 0.85 el modelo propone más de lo pedido
UMBRAL_AMPLIACION = 0.85


def _escalon(valor, tramos, default):
    """Devuelve el puntaje del primer tramo que cumple. tramos: [(prueba, puntaje)]"""
    if valor is None:
        return None
    for prueba, puntaje in tramos:
        if prueba(valor):
            return puntaje
    return default


def _promedio(valores):
    limpios = [v for v in valores if isinstance(v, (int, float))]
    return sum(limpios) / len(limpios) if limpios else None


def _div(numerador, denominador, si_cero_cero=None, si_denominador_cero=None):
    """División que distingue 'no hay dato' de 'el dato es cero'.

    Es el corazón de la corrección más importante. Antes, cualquier división
    con denominador en cero tumbaba el módulo completo con un #DIV/0!.
    """
    if numerador is None or denominador is None:
        return None
    if denominador == 0:
        return si_cero_cero if numerador == 0 else si_denominador_cero
    return numerador / denominador


# ─────────────────────────────────────────────────────────────────────────────
# Módulo 1 · Perfil de empresa
# ─────────────────────────────────────────────────────────────────────────────
def _perfil_empresa(p, hoy):
    v = {}

    v["estado"] = (0.15, {"Codigo 1": 1.0, "Codigo 2": 0.75, "Codigo 3": 0.5}
                   .get(p.get("estado")))

    fc = p.get("fecha_constitucion")
    antiguedad = (hoy - fc).days / 365 if fc else None
    v["antiguedad"] = (0.25, _escalon(antiguedad, [
        (lambda x: x >= 9, 1.0), (lambda x: x >= 4, 0.7), (lambda x: x >= 2, 0.5)], 0.25))

    v["giro"] = (0.30, {"Codigo 1": 1.0, "Codigo 2": 0.8, "Codigo 3": 0.65,
                        "Codigo 4": 0.5, "Codigo 5": 0.3, "Codigo 6": 0.15}
                 .get(p.get("giro")))

    redes = p.get("presencia_redes")
    v["presencia_redes"] = (0.15, None if redes is None else
                            {"Alta": 1.0, "Media": 0.75, "Baja": 0.5,
                             "Sin redes/página": 0.25}.get(redes, 0.0))

    proc = p.get("procedencia")
    v["procedencia"] = (0.15, None if proc is None else
                        {"Conocido Nea": 1.0, "Referido Cliente": 0.75,
                         "Linkedin/Expo": 0.5}.get(proc, 0.25))
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Módulo 2 · Buró de crédito
# ─────────────────────────────────────────────────────────────────────────────
def _buro(b, legado):
    v, vetos = {}, []

    mora = b.get("ocurrencias_mora")
    if mora is not None and mora >= 4:
        vetos.append("exclusion")
    v["ocurrencias_mora"] = (0.15, _escalon(mora, [
        (lambda x: x == 0, 1.0), (lambda x: 0 < x < 4, 0.0)],
        # CORRECCIÓN 7: antes esta rama devolvía el texto "Exclusion" dentro de
        # una suma ponderada. La exclusión ahora es un veto aparte.
        "Exclusion" if legado else 0.0))

    # CORRECCIÓN 1: sin saldo actual no hay deuda, así que no hay nada vencido.
    # Antes era una división entre cero que tumbaba el módulo completo.
    cubierto = (_div(b.get("saldo_vencido"), b.get("saldo_actual"))
                if legado else
                _div(b.get("saldo_vencido"), b.get("saldo_actual"),
                     si_cero_cero=0.0, si_denominador_cero=1.0))
    v["porcentaje_cubierto"] = (0.10, _escalon(cubierto, [
        (lambda x: x == 0, 1.0), (lambda x: 0 < x < 0.25, 0.9)], 0.5))

    # CORRECCIÓN 4: un peor estado de 0 significa sin historial de mora, o sea
    # lo mejor. Antes caía al último tramo y recibía −2, la pena máxima.
    peor = b.get("peor_edo_6m")
    if legado:
        v["peor_edo"] = (0.15, _escalon(peor, [
            (lambda x: x == 1, 1.0), (lambda x: x == 2, 0.0),
            (lambda x: x == 3, -1.0)], -2.0))
    else:
        v["peor_edo"] = (0.15, _escalon(peor, [
            (lambda x: x in (0, 1), 1.0), (lambda x: x == 2, 0.0),
            (lambda x: x == 3, -1.0)], -2.0))

    v["no_consultas"] = (0.15, _escalon(b.get("consultas_12m"), [
        (lambda x: x < 7, 1.0), (lambda x: x < 11, 0.7)], -0.25))

    # CORRECCIÓN 1 (bis): sin créditos abiertos no hay proporción que calcular.
    abiertos = (_div(b.get("creditos_abiertos_ultimo_ano"), b.get("creditos_abiertos"))
                if legado else
                _div(b.get("creditos_abiertos_ultimo_ano"), b.get("creditos_abiertos"),
                     si_cero_cero=0.0, si_denominador_cero=0.0))
    v["porcentaje_creditos_abiertos"] = (0.15, _escalon(abiertos, [
        (lambda x: x < 0.4, 1.0), (lambda x: x <= 0.6, 0.6)], 0.3))

    v["no_avales"] = (0.10, _escalon(b.get("avales"), [
        (lambda x: x == 0, 1.0), (lambda x: x <= 3, 0.0)], -1.0))

    # CORRECCIÓN 6: el escalón en 0.30 daba un salto de 2.31 puntos —con 0.30
    # recibías −2 y con 0.31 recibías 0.31—. Ahora la penalización se reparte
    # de forma continua y los extremos siguen valiendo lo mismo.
    score = b.get("score_pyme")
    adj = None if score is None else (score - 100) / 300
    if adj is None:
        v["score_pyme_adj"] = (0.20, None)
    elif legado:
        v["score_pyme_adj"] = (0.20, -2.0 if adj <= 0.3 else adj)
    else:
        v["score_pyme_adj"] = (0.20, adj if adj > 0.3
                               else -2.0 + (max(adj, 0.0) / 0.3) * 2.3)

    prev = b.get("prevenciones")
    if prev == "Roja":
        vetos.append("exclusion")
    elif prev == "Amarilla":
        vetos.append("comite")
    # CORRECCIÓN 7 (bis): pesa 0.00, pero en legado metía texto en el cálculo.
    v["prevenciones"] = (0.0, ({None: 1.0, "": 1.0, 0: 1.0}.get(prev, prev)
                               if legado else 1.0))
    return v, vetos


# ─────────────────────────────────────────────────────────────────────────────
# Módulo 3 · Estados de cuenta
# ─────────────────────────────────────────────────────────────────────────────
def _edos_cuenta(cuentas, monto, legado):
    """`cuentas` es una lista de cuentas bancarias; cada una trae sus periodos
    ordenados del más reciente al más antiguo, como en el Excel."""
    v = {}
    # CORRECCIÓN 8: las fórmulas del Excel solo leían dos bloques de cuentas,
    # así que un cliente con tres cuentas se analizaba con dos, en silencio.
    usadas = cuentas[:2] if legado else cuentas
    periodos = [p for c in usadas for p in c]

    movimientos = ([p.get("num_depositos") for p in periodos] +
                   [p.get("num_retiros") for p in periodos])
    v["no_prom_movimientos"] = (0.10, _escalon(_promedio(movimientos), [
        (lambda x: x >= 40, 1.0), (lambda x: x > 30, 0.75),
        (lambda x: x > 15, 0.5)], 0.3))

    # Saldo inicial: el del periodo más antiguo de cada cuenta. Saldo final: el
    # del más reciente. Antes esas celdas apuntaban a filas fijas, lo que asumía
    # exactamente tres estados por cuenta.
    inicial = sum(c[-1]["saldo_inicial"] for c in usadas
                  if c and c[-1].get("saldo_inicial") is not None)
    final = sum(c[0]["saldo_final"] for c in usadas
                if c and c[0].get("saldo_final") is not None)
    cambio = None if not inicial else (final / inicial - 1)
    v["cambio_balance"] = (0.25, _escalon(cambio, [
        (lambda x: x >= 0.25, 1.0), (lambda x: x > 0, 0.75),
        (lambda x: x > -0.25, 0.5)], 0.0))

    def suma_promedios(campo):
        """Suma el promedio de cada cuenta, como hace el Excel: es el saldo
        típico del cliente sumando todas sus cuentas, no el promedio global."""
        por_cuenta = [_promedio([p.get(campo) for p in c]) for c in usadas]
        limpios = [x for x in por_cuenta if x is not None]
        return sum(limpios) if limpios else None

    prom = _div(suma_promedios("saldo_promedio"), monto)
    v["balance_prom_entre_monto"] = (0.35, _escalon(prom, [
        (lambda x: x >= 2, 1.0), (lambda x: x > 1.5, 0.75),
        (lambda x: x > 1, 0.5), (lambda x: x > 0.74, 0.25)], 0.0))

    mini = _div(suma_promedios("saldo_min"), monto)
    v["min_bal_entre_monto"] = (0.10, _escalon(mini, [
        (lambda x: x >= 1, 1.0), (lambda x: x > 0.75, 0.75),
        (lambda x: x > 0.5, 0.5), (lambda x: x > 0.25, 0.25)], 0.0))

    maxi = _div(suma_promedios("saldo_max"), monto)
    v["max_bal_entre_monto"] = (0.20, _escalon(maxi, [
        (lambda x: x >= 5, 1.0), (lambda x: x > 4, 0.75),
        (lambda x: x > 2, 0.5), (lambda x: x > 1, 0.25)], -0.5))
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Módulo 4 · Declaración anual
# ─────────────────────────────────────────────────────────────────────────────
def _declaracion_anual(d, monto, legado):
    v = {}

    ingreso = _div(d.get("ingresos_totales"), 12)
    v["ingreso_entre_monto"] = (0.25, _escalon(_div(ingreso, monto), [
        (lambda x: x >= 5, 1.0), (lambda x: x > 2.5, 0.75),
        (lambda x: x > 1, 0.5)], 0.0))

    # PENDIENTE DE DECISIÓN: los ingresos se dividen entre 12 y la utilidad
    # entre 6. No hay razón aparente para que difieran; si el 6 debía ser 12,
    # esta variable sobrestima al doble y pesa 25% del módulo. Se deja como
    # está porque cambiarlo es decisión de negocio, no corrección de defecto.
    utilidad = _div(d.get("utilidad_operacion"), 6)
    v["utilidad_entre_monto"] = (0.25, _escalon(_div(utilidad, monto), [
        (lambda x: x >= 1, 1.0), (lambda x: x > 0.5, 0.75),
        (lambda x: x > 0.3, 0.5)], 0.0))

    # CORRECCIÓN 2: un balance vacío no es un balance malo. Antes, activo y
    # pasivo en cero producían #DIV/0! y tumbaban el módulo completo.
    liquidez = (_div(d.get("activo_corto_plazo"), d.get("pasivo_corto_plazo"))
                if legado else
                _div(d.get("activo_corto_plazo"), d.get("pasivo_corto_plazo"),
                     si_cero_cero=None, si_denominador_cero=1.5))
    v["razon_liquidez"] = (0.20, _escalon(liquidez, [
        (lambda x: x >= 1.5, 1.0), (lambda x: x > 1, 0.75),
        (lambda x: x > 0.7, 0.35)], 0.0))

    acp, inv = d.get("activo_corto_plazo"), d.get("inventarios")
    neto = None if acp is None else acp - (inv or 0)
    acido = (_div(neto, d.get("pasivo_corto_plazo")) if legado else
             _div(neto, d.get("pasivo_corto_plazo"),
                  si_cero_cero=None, si_denominador_cero=1.25))
    v["acid_test"] = (0.10, _escalon(acido, [
        (lambda x: x >= 1.25, 1.0), (lambda x: x > 0.75, 0.75),
        (lambda x: x > 0.5, 0.35)], 0.0))

    v["capital_contable_entre_monto"] = (0.20, _escalon(
        _div(d.get("capital_contable"), monto), [
            (lambda x: x >= 5, 1.0), (lambda x: x > 2.5, 0.7),
            (lambda x: x > 1, 0.3)], 0.0))

    dic = d.get("dictaminados")
    v["edos_financieros_dictaminados"] = (0.20, None if dic is None else
                                          (1.0 if dic == "Si" else 0.0))
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Ponderación
# ─────────────────────────────────────────────────────────────────────────────
def _ponderar(variables, legado):
    """Promedio ponderado sobre las variables disponibles.

    CORRECCIÓN 5: en legado las ponderaciones de declaración anual sumaban
    1.20, así que ese módulo salía inflado un 20%. Renormalizar sobre lo
    disponible lo arregla solo, y de paso hace que el archivo aguante que
    alguien agregue o quite una variable sin recalcular los pesos a mano.
    """
    num = den = 0.0
    for peso, puntaje in variables.values():
        if puntaje is None or isinstance(puntaje, str):
            continue
        num += peso * puntaje
        den += peso
    if den == 0:
        return None
    return num / den if not legado else num


def evaluar(perfil, buro, declaracion, cuentas, hoy=None, legado=False):
    """Devuelve el score con su desglose completo por módulo y variable."""
    hoy = hoy or date.today()
    monto = perfil.get("monto_solicitado")

    vars_buro, vetos = _buro(buro, legado)
    modulos = {
        "perfil_empresa": _perfil_empresa(perfil, hoy),
        "buro": vars_buro,
        "edos_cuenta": _edos_cuenta(cuentas, monto, legado),
        "declaracion_anual": _declaracion_anual(declaracion, monto, legado),
    }

    resultados, num, den = {}, 0.0, 0.0
    for nombre, variables in modulos.items():
        r = _ponderar(variables, legado)
        resultados[nombre] = r
        # CORRECCIÓN 3: la degradación elegante no operaba porque el error se
        # propagaba aunque la bandera fuera 0. Y un módulo que sacaba
        # exactamente 0 —la peor calificación— se contaba como ausente y se
        # caía del promedio, subiendo el score en lugar de bajarlo.
        if r is not None:
            num += PESOS_MODULO[nombre] * r
            den += PESOS_MODULO[nombre]

    score = None if den == 0 else num / den

    if "exclusion" in vetos:
        veredicto, monto_aprobado = "Rechazado", 0.0
    elif score is None:
        veredicto, monto_aprobado = "Sin datos suficientes", 0.0
    elif "comite" in vetos:
        veredicto, monto_aprobado = "Comité", 0.0
    elif score >= UMBRAL_AMPLIACION:
        veredicto, monto_aprobado = "Aprobado", monto * FACTOR_AMPLIACION
    elif score >= UMBRAL_APROBADO:
        veredicto, monto_aprobado = "Aprobado", monto
    elif score >= UMBRAL_COMITE:
        veredicto, monto_aprobado = "Comité", 0.0
    else:
        veredicto, monto_aprobado = "Rechazado", 0.0

    return {
        "score": score,
        "veredicto": veredicto,
        "monto_solicitado": monto,
        "monto_aprobado": monto_aprobado,
        "vetos": vetos,
        "modulos": resultados,
        "variables": {m: {k: {"peso": p, "puntaje": s} for k, (p, s) in vs.items()}
                      for m, vs in modulos.items()},
        "modulos_sin_datos": [m for m, r in resultados.items() if r is None],
    }
