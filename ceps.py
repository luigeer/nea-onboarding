# -*- coding: utf-8 -*-
"""
ceps.py — Movimientos SPEI listos para comprobar en Banxico
===========================================================
Un estado de cuenta lo puede editar cualquiera con un PDF. El CEP —el
Comprobante Electrónico de Pago que emite Banco de México— no: se consulta en
banxico.org.mx/cep con la clave de rastreo y devuelve lo que el sistema de pagos
registró. Comprobar los movimientos grandes contra el CEP es lo que convierte
un estado de cuenta en evidencia.

**Solo el SPEI tiene CEP.** Un traspaso entre dos cuentas del mismo banco no
pasa por el sistema de pagos interbancario, así que no genera comprobante y no
se puede verificar por esta vía. Eso importa en este expediente: los depósitos
que recibe La Llosa son traspasos internos dentro de Banco del Bajío, no SPEI.
No se pueden comprobar con CEP, y decir que "no se comprobaron" sin explicar por
qué sería injusto.

**La línea resumen engaña.** Banco del Bajío escribe "ENVÍO SPEI:LA LLOSA" en el
renglón del movimiento, donde "LA LLOSA" es el nombre del ORDENANTE, no del
beneficiario. El beneficiario real vive en el bloque de detalle de abajo. Leer
solo el renglón lleva a concluir que la empresa se transfiere a sí misma cuando
en realidad le está pagando a un tercero. Este módulo lee el detalle.
"""

import re

# Banco del Bajío escribe el detalle de cada SPEI en renglones que siguen al
# movimiento. Estas son las etiquetas, tal como salen del PDF.
RE_FECHA = re.compile(r"^\s*(\d{1,2})\s+(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\b")
RE_IMPORTES = re.compile(r"\$\s*([\d,]+\.\d{2})")
RE_CAMPO = {
    "institucion_receptora": re.compile(r"INSTITUCIÓN RECEPTORA:\s*(.+?)\s*$"),
    "institucion_ordenante": re.compile(r"INSTITUCIÓN ORDENANTE:\s*(.+?)\s*$"),
    "beneficiario":          re.compile(r"BENEFICIARIO:\s*(.+?)\s*$"),
    "cuenta_beneficiaria":   re.compile(r"CUENTA BENEFICIARIA:\s*([\d]+)"),
    "cuenta_ordenante":      re.compile(r"CUENTA ORDENANTE:\s*([\d]+)"),
    "clave_rastreo":         re.compile(r"CLAVE DE RASTREO:\s*([A-Z0-9]+)"),
    "referencia":            re.compile(r"REFERENCIA:\s*(\d+)"),
    "hora":                  re.compile(r"HORA:\s*([\d:]+)"),
    "ordenante":             re.compile(r"ORDENANTE:\s*(.+?)\s*(?:\(BI-|$)"),
    # La domiciliación no genera CEP, pero el banco sí imprime quién cobró y con
    # qué RFC. Eso permite confirmar la contraparte aunque no haya comprobante
    # de Banxico: es más de lo que se puede decir de un traspaso interno.
    "emisor_domiciliacion":  re.compile(r"EMISOR:\s*(.+?)\s*$"),
    "rfc_contraparte":       re.compile(r"RFC:\s*([A-Z0-9&]{10,13})"),
    "rastreo_domiciliacion": re.compile(r"RASTREO:\s*([\d\-]+)"),
}

MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}

# El texto extraído mete espacios dentro de las primeras palabras: "E N VÍO SPEI"
# en lugar de "ENVÍO SPEI". Se normaliza antes de clasificar.
def _limpiar(t):
    t = re.sub(r"\bE\s*N\s*VÍO\b", "ENVÍO", t)
    t = re.sub(r"\bR\s*E\s*CEPCIÓN\b", "RECEPCIÓN", t)
    t = re.sub(r"\bR\s*E\s*TIRO\b", "RETIRO", t)
    t = re.sub(r"\bC\s*O\s*MISION\b", "COMISION", t)
    t = re.sub(r"\bT\s*R\s*ASPASO\b", "TRASPASO", t)
    return re.sub(r"\s+", " ", t).strip()


def _clasificar(desc):
    d = desc.upper()
    if "ENVÍO SPEI" in d or "ENVIO SPEI" in d:
        return "spei_enviado"
    if "RECEPCIÓN SPEI" in d or "RECEPCION SPEI" in d or "SPEI RECIBIDO" in d:
        return "spei_recibido"
    if "TRASPASO" in d:
        return "traspaso_interno"
    if "DOMICILIACION" in d or "DOMICILIACIÓN" in d:
        return "domiciliacion"
    if "COMISION" in d or "IVA" in d:
        return "comision"
    return "otro"


def movimientos(ruta, anio):
    """Lee un estado de cuenta de Banco del Bajío y devuelve sus movimientos.

    Cada movimiento trae su bloque de detalle ya interpretado, así que el
    beneficiario es el real y no el nombre del ordenante que aparece en el
    renglón resumen.
    """
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        renglones = []
        for p in pdf.pages:
            renglones.extend((p.extract_text() or "").split("\n"))

    fuera, actual = [], None
    for cruda in renglones:
        linea = _limpiar(cruda)
        m = RE_FECHA.match(cruda)
        if m and RE_IMPORTES.search(linea):
            if actual:
                fuera.append(actual)
            importes = [float(x.replace(",", "")) for x in RE_IMPORTES.findall(linea)]
            desc = re.sub(r"\$\s*[\d,]+\.\d{2}", "", linea)
            desc = RE_FECHA.sub("", desc).strip()
            actual = {
                "fecha": "%s-%02d-%02d" % (anio, MESES[m.group(2)], int(m.group(1))),
                "descripcion": desc,
                "tipo": _clasificar(desc),
                # El primer importe es el movimiento y el último el saldo; cuando
                # solo hay uno, el renglón trae saldo y el monto viene aparte.
                "monto": importes[0] if len(importes) > 1 else None,
                "saldo": importes[-1],
            }
            continue
        if actual is None:
            continue
        for campo, patron in RE_CAMPO.items():
            hallado = patron.search(linea)
            if hallado and campo not in actual:
                actual[campo] = hallado.group(1).strip()
    if actual:
        fuera.append(actual)
    return fuera


def comprobables(movs, minimo=0.0):
    """Los movimientos que SÍ tienen CEP, ordenados de mayor a menor monto.

    Un movimiento sin clave de rastreo no es comprobable por esta vía, y eso no
    lo hace sospechoso: un traspaso interno simplemente no pasa por SPEI.
    """
    con = [m for m in movs if m.get("clave_rastreo") and (m.get("monto") or 0) >= minimo]
    return sorted(con, key=lambda m: -(m.get("monto") or 0))


def sin_cep(movs, minimo=0.0):
    """Los movimientos relevantes que no se pueden comprobar con CEP, y por qué."""
    fuera = []
    for m in movs:
        if m.get("clave_rastreo") or (m.get("monto") or 0) < minimo:
            continue
        if m["tipo"] == "traspaso_interno":
            razon = "traspaso entre cuentas del mismo banco: no pasa por SPEI"
        elif m["tipo"] == "domiciliacion":
            razon = "cargo por domiciliación: lo autoriza el banco, no genera CEP"
        elif m["tipo"] == "comision":
            razon = "comisión del banco"
        else:
            razon = "el estado de cuenta no trae clave de rastreo"
        fuera.append(dict(m, razon_sin_cep=razon))
    return sorted(fuera, key=lambda m: -(m.get("monto") or 0))


URL_CEP = "https://www.banxico.org.mx/cep/"


def instrucciones(m):
    """Los datos exactos que pide el formulario de Banxico para un movimiento."""
    return {
        "url": URL_CEP,
        "fecha_operacion": m["fecha"],
        "criterio": "Clave de rastreo",
        "clave_rastreo": m.get("clave_rastreo"),
        "banco_emisor": "BanBajío",
        "banco_receptor": m.get("institucion_receptora") or m.get("institucion_ordenante"),
        "cuenta_beneficiaria": m.get("cuenta_beneficiaria"),
        "monto": m.get("monto"),
        "beneficiario_declarado": m.get("beneficiario"),
    }
