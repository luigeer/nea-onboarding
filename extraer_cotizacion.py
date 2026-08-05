# -*- coding: utf-8 -*-
"""
extraer_cotizacion.py — Extracción determinista de la cotización de Nea
========================================================================
La cotización la genera Nea, así que su PDF trae capa de texto y se parsea sin
modelo. Aporta la línea solicitada, la mensualidad y las condiciones comerciales,
más la verificación de que la cotización siga vigente.

Advertencia de alcance: la cotización NO es evidencia de línea autorizada. Lo que
se extrae aquí alimenta credito.solicitada; credito.autorizada la registra riesgo.

Uso:
    python extraer_cotizacion.py <cotizacion.pdf> [salida.json]
"""

import json
import re
import sys
from datetime import date

import pdfplumber

X_TOL = 1.5

MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
         "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11,
         "DICIEMBRE": 12}

RE_MONTO = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


def _monto(txt):
    m = RE_MONTO.search(txt or "")
    return float(m.group(1).replace(",", "")) if m else None


def _iso(txt):
    """'31 de Julio de 2026' -> '2026-07-31'"""
    m = re.search(r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})", txt or "", re.I)
    if not m:
        return None
    mes = m.group(2).upper()
    mes = mes.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    if mes not in MESES:
        return None
    return "%s-%02d-%02d" % (m.group(3), MESES[mes], int(m.group(1)))


def _num(patron, texto, cast=float):
    m = re.search(patron, texto, re.I)
    if not m:
        return None
    try:
        return cast(m.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None


def extraer_cotizacion(ruta_pdf):
    with pdfplumber.open(ruta_pdf) as pdf:
        lineas = []
        for p in pdf.pages:
            lineas += [l.strip() for l in (p.extract_text(x_tolerance=X_TOL) or "").split("\n")
                       if l.strip()]
    texto = " ".join(lineas)
    alertas = []

    # El nombre del encabezado es comercial y puede no coincidir con la razón
    # social de la CSF. Se guarda como declarado, nunca como validado.
    nombre_declarado = lineas[0] if lineas else None

    # "$ 20,700 / al mes" y "$ 900,000 / FINANCIAMIENTO": el monto precede a su etiqueta.
    mensualidad = linea = None
    for i, l in enumerate(lineas):
        if re.match(r"^al\s+mes$", l, re.I) and i > 0:
            mensualidad = _monto(lineas[i - 1])
        if re.match(r"^FINANCIAMIENTO$", l, re.I) and i > 0:
            linea = _monto(lineas[i - 1])
    if linea is None or mensualidad is None:
        montos = [_monto(l) for l in lineas if _monto(l) is not None]
        if len(montos) >= 2:
            linea = linea if linea is not None else max(montos)
            mensualidad = mensualidad if mensualidad is not None else min(montos)
            alertas.append("Línea y mensualidad se dedujeron por magnitud y no por etiqueta; "
                           "el formato de la cotización cambió. Verificar.")

    periodicidad = None
    m = re.search(r"d[ií]as?\s+de\s+pago\s+despu[eé]s\s+del\s+corte\s+(\w+)", texto, re.I)
    if m:
        periodicidad = m.group(1).capitalize()

    vigencia = _iso(next((l for l in lineas if re.search(r"vigencia", l, re.I)), ""))
    if vigencia:
        a, mm, d = (int(x) for x in vigencia.split("-"))
        dias = (date(a, mm, d) - date.today()).days
        if dias < 0:
            alertas.append("Cotización vencida el %s. El precio ya no está respaldado." % vigencia)
        elif dias <= 7:
            alertas.append("Cotización vence en %d día(s), el %s." % (dias, vigencia))

    datos = {
        "nombre_declarado": nombre_declarado,
        "linea": linea,
        "mensualidad": mensualidad,
        "periodicidad": periodicidad,
        "dias_pago_tras_corte": _num(r"(\d+)\s*d[ií]as?\s+de\s+pago", texto, int),
        "comision_retiro_efectivo_pct": _num(r"retiro\s+de\s+efectivo:\s*([\d\.]+)\s*%", texto),
        "costo_envio_tarjetas": _num(r"env[ií]o\s+de\s+tarjetas:\s*\$\s*([\d,\.]+)", texto),
        "tasa_moratoria_anual_pct": _num(r"morator[ií]a:\s*([\d\.]+)\s*%", texto),
        "comision_pago_tardio": _num(r"pago\s+tard[ií]o\s*:?\s*\$\s*([\d,\.]+)", texto),
        "tarjetas_fisicas": "Ilimitadas" if re.search(r"TARJETAS\s+FISICAS\s+ILIMITADAS",
                                                      texto, re.I) else None,
        "tarjetas_virtuales": "Ilimitadas" if re.search(r"TARJETAS\s+VIRTUALES\s+ILIMITADAS",
                                                        texto, re.I) else None,
        "iva_incluido": not bool(re.search(r"no\s+incluyen\s+IVA", texto, re.I)),
        "vigencia": vigencia,
        "alertas": alertas,
    }
    if datos["linea"] is None:
        raise ValueError("No se encontró la línea de financiamiento. ¿Es una cotización de Nea?")
    return datos


def a_expediente(cot, exp):
    """Vuelca la cotización en credito.solicitada y en las condiciones comerciales."""
    exp["credito"]["solicitada"].update({
        "linea": cot["linea"],
        "mensualidad": cot["mensualidad"],
        "plazo": cot.get("periodicidad"),
        "tarjetas": cot.get("tarjetas_fisicas"),
    })
    exp["condiciones_comerciales"] = {
        k: cot.get(k) for k in ("dias_pago_tras_corte", "comision_retiro_efectivo_pct",
                                "costo_envio_tarjetas", "tasa_moratoria_anual_pct",
                                "comision_pago_tardio", "tarjetas_fisicas",
                                "tarjetas_virtuales", "iva_incluido", "vigencia")
    }
    if cot.get("nombre_declarado"):
        exp["cliente"]["declarado"]["razon_social"] = cot["nombre_declarado"]

    fuente = "Cotización con vigencia al %s" % (cot.get("vigencia") or "fecha s/d")
    for campo in ("linea_solicitada", "mensualidad"):
        exp["procedencia"][campo] = fuente
    exp["documentos"].append({"tipo": "cotizacion", "fecha_emision": None,
                              "vigente_hasta": cot.get("vigencia"), "legible": True,
                              "superado_por": None})

    # Discrepancia de nombre entre la cotización y la CSF: es observación, no error.
    validada = exp["cliente"]["validado"].get("razon_social")
    declarada = cot.get("nombre_declarado")
    if validada and declarada:
        base = re.sub(r"[^A-Z]", "", declarada.upper())
        if base and base not in re.sub(r"[^A-Z]", "", validada.upper()):
            exp["observaciones"].append({
                "tipo": "razon_social_discrepante", "severidad": "advertencia",
                "descripcion": ("La cotización dice %r y la CSF dice %r. El contrato se emite "
                                "con la denominación de la CSF." % (declarada, validada)),
                "estado": "abierta", "fecha": date.today().isoformat()})
    for a in cot.get("alertas", []):
        exp["observaciones"].append({"tipo": "cotizacion", "descripcion": a,
                                     "severidad": "advertencia", "estado": "abierta",
                                     "fecha": date.today().isoformat()})
    return exp


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    d = extraer_cotizacion(sys.argv[1])
    salida = json.dumps(d, ensure_ascii=False, indent=2)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            fh.write(salida)
        print("Escrito: %s" % sys.argv[2])
    else:
        print(salida)
