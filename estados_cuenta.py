# -*- coding: utf-8 -*-
"""
estados_cuenta.py — Del Bank Statement Analyzer al modelo de riesgo
====================================================================
El analizador ya produce, por cada estado de cuenta, exactamente las cifras
que el modelo consume. Este módulo las traduce y de paso resuelve tres cosas
que el Excel no cubría.

**Moneda.** El Excel sumaba los saldos de todas las cuentas sin mirar la
divisa, así que una cuenta en dólares entraba como si fueran pesos y
subestimaba al cliente por un factor de casi veinte. Aquí una cuenta que no
esté en pesos exige tipo de cambio, o se detiene.

**Flujo operativo contra cifras de encabezado.** La memoria del analizador lo
dice con todas sus letras: los ciclos de inversión overnight inflan los conteos
de movimientos, y la línea debe anclarse al ingreso operativo recurrente y no
al volumen bruto de depósitos. Si la ficha trae las cifras reconciliadas, se
usan esas; si no, se usan las de encabezado y queda registrado el aviso.

**Orden de los periodos.** El modelo necesita saber cuál es el más reciente y
cuál el más antiguo para calcular el cambio de balance. Se ordena por fecha en
lugar de confiar en el orden en que llegaron.

Formato de entrada: la lista de objetos "Informacion Bancaria" que devuelve el
analizador, tal cual.
"""

from datetime import date, datetime

MONEDA_BASE = "MXN"

# La ficha del analizador y el modelo nombran distinto las mismas cifras.
CAMPOS = {
    "saldo_inicial": "saldo_inicial",
    "numero_depositos": "num_depositos",
    "monto_depositos": "monto_depositos",
    "numero_retiros": "num_retiros",
    "monto_retiros": "monto_retiros",
    "saldo_final": "saldo_final",
    "saldo_promedio": "saldo_promedio",
    "saldo_minimo": "saldo_min",
    "saldo_maximo": "saldo_max",
}

# Cifras reconciladas: si el analizador las provee, tienen prioridad sobre las
# de encabezado. Hoy su JSON no las incluye, pero el reporte narrativo sí las
# calcula, así que agregarlas es cuestión de exponerlas.
CAMPOS_OPERATIVOS = {
    "numero_depositos_operativo": "num_depositos",
    "numero_retiros_operativo": "num_retiros",
    "monto_depositos_operativo": "monto_depositos",
    "monto_retiros_operativo": "monto_retiros",
}

SALDOS = ("saldo_inicial", "saldo_final", "saldo_promedio", "saldo_min", "saldo_max")


class DatosInsuficientes(ValueError):
    pass


def _fecha(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if not v:
        return None
    texto = str(v).strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _numero(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    limpio = str(v).replace("$", "").replace(",", "").replace(" ", "").strip()
    if limpio.startswith("(") and limpio.endswith(")"):
        limpio = "-" + limpio[1:-1]
    try:
        return float(limpio)
    except ValueError:
        return None


def desde_analizador(fichas, tipo_cambio=None, usar_operativo=True):
    """Traduce las fichas del analizador a las cuentas que consume el modelo.

    `tipo_cambio` es un dict {divisa: pesos_por_unidad}, por ejemplo
    {"USD": 18.4}. Solo hace falta si alguna cuenta no está en pesos.

    Devuelve (cuentas, avisos). `cuentas` es una lista de cuentas, cada una con
    sus periodos del más reciente al más antiguo, como espera modelo_riesgo.
    """
    tipo_cambio = {k.upper(): v for k, v in (tipo_cambio or {}).items()}
    tipo_cambio.setdefault(MONEDA_BASE, 1.0)
    avisos, por_cuenta = [], {}

    for i, f in enumerate(fichas):
        ficha = f.get("Informacion Bancaria", f)
        banco = (ficha.get("banco") or "?").strip()
        cuenta = str(ficha.get("cuenta_bancaria") or "?").strip()
        divisa = (ficha.get("moneda") or MONEDA_BASE).strip().upper()

        if divisa not in tipo_cambio:
            raise DatosInsuficientes(
                "El estado de cuenta %d de %s está en %s y no se dio tipo de cambio. "
                "Sumar divisas distintas como si fueran la misma distorsiona el "
                "análisis: pásalo como tipo_cambio={'%s': <pesos por unidad>}."
                % (i + 1, banco, divisa, divisa))
        factor = tipo_cambio[divisa]

        periodo = {"_fin": _fecha(ficha.get("fecha_final")),
                   "_inicio": _fecha(ficha.get("fecha_inicial"))}
        for origen, destino in CAMPOS.items():
            periodo[destino] = _numero(ficha.get(origen))

        if usar_operativo:
            reconciliados = [d for o, d in CAMPOS_OPERATIVOS.items()
                             if _numero(ficha.get(o)) is not None]
            for origen, destino in CAMPOS_OPERATIVOS.items():
                valor = _numero(ficha.get(origen))
                if valor is not None:
                    periodo[destino] = valor
            if reconciliados:
                periodo["_operativo"] = True
            else:
                periodo["_operativo"] = False

        for campo in SALDOS:
            if periodo.get(campo) is not None and factor != 1.0:
                periodo[campo] = periodo[campo] * factor
        if factor != 1.0:
            avisos.append("La cuenta %s de %s está en %s; se convirtió a pesos a %.4f."
                          % (cuenta, banco, divisa, factor))

        faltantes = [d for d in CAMPOS.values() if periodo.get(d) is None]
        if faltantes:
            avisos.append("Al estado de cuenta %d de %s (cuenta %s) le faltan cifras: %s."
                          % (i + 1, banco, cuenta, ", ".join(faltantes)))

        por_cuenta.setdefault((banco, cuenta, divisa), []).append(periodo)

    if not por_cuenta:
        raise DatosInsuficientes("No se recibió ningún estado de cuenta.")

    # El modelo lee el primer periodo como el más reciente y el último como el
    # más antiguo, así que el orden no puede depender de cómo llegaron.
    cuentas = []
    for (banco, cuenta, divisa), periodos in sorted(por_cuenta.items()):
        sin_fecha = [p for p in periodos if p["_fin"] is None]
        if sin_fecha:
            avisos.append("La cuenta %s de %s tiene %d estado(s) sin fecha; el orden "
                          "puede quedar mal y con él el cambio de balance."
                          % (cuenta, banco, len(sin_fecha)))
        periodos.sort(key=lambda p: p["_fin"] or date.min, reverse=True)
        cuentas.append(periodos)

    if usar_operativo and not any(p.get("_operativo") for c in cuentas for p in c):
        avisos.append(
            "Ninguna ficha trae cifras reconciliadas, así que se usan las de "
            "encabezado. Los ciclos de inversión overnight y los traspasos entre "
            "cuentas propias inflan el conteo de movimientos y el saldo máximo, "
            "que son dos de las cinco variables del módulo.")

    return cuentas, avisos


def resumen(cuentas):
    """Una línea por cuenta, para el reporte al comité."""
    out = []
    for i, periodos in enumerate(cuentas, 1):
        fechas = [p["_fin"] for p in periodos if p["_fin"]]
        out.append({
            "cuenta": i,
            "periodos": len(periodos),
            "del": min(fechas).isoformat() if fechas else None,
            "al": max(fechas).isoformat() if fechas else None,
            "saldo_promedio": sum(p["saldo_promedio"] for p in periodos
                                  if p.get("saldo_promedio") is not None) / len(periodos),
            "reconciliado": all(p.get("_operativo") for p in periodos),
        })
    return out


def a_expediente(cuentas, exp, titular=None):
    """Registra las cuentas en el expediente, para las compuertas de la etapa 6.

    La compuerta cuenta periodos por la cuenta del cliente: tres estados, o seis
    si la línea autorizada supera los $200,000.
    """
    exp["cuentas_bancarias"] = []
    for periodos in cuentas:
        exp["cuentas_bancarias"].append({
            "banco": None, "clabe": None, "divisa": MONEDA_BASE,
            "titular": titular,
            "titular_es_cliente": True,
            "periodos": [p["_fin"].strftime("%Y-%m") for p in periodos if p["_fin"]],
            "cifras": [{k: v for k, v in p.items() if not k.startswith("_")}
                       for p in periodos],
        })
    return exp
