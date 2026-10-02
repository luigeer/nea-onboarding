# -*- coding: utf-8 -*-
"""
santander.py — Lee los estados de cuenta CUENTA SANTANDER PYME
================================================================
Cuarto banco después de BBVA, Mifel y Banco del Bajío (este último solo para
CEPs, en `ceps.py`). Una tabla con tres columnas de importes —DEPOSITO, RETIRO y
SALDO— y una línea "TOTAL depósitos retiros" al cierre.

**Las letras duplicadas.** Santander imprime la mitad de los renglones en
negritas simulando cada carácter dos veces, una encima de la otra. Leído tal
cual sale "0011--JJUUNN--22002266". `dedupe_chars()` de pdfplumber quita el
carácter repetido en la misma posición; sin eso ningún renglón en negritas se
reconoce como movimiento.

**Por qué por posición.** Igual que en Mifel: el importe de un movimiento cae
en la columna DEPOSITO o en la de RETIRO, y en el texto extraído se ven iguales.
La dirección se decide por la coordenada horizontal del número, comparada con el
punto medio entre las dos columnas del encabezado de la tabla.

**La comprobación.** Santander imprime el saldo después de cada movimiento y el
total de depósitos y de retiros: `cuadra` reconstruye la cadena de saldos
renglón por renglón y compara los totales. Es la misma regla que Mifel.

**Los SPEI.** Debajo de cada transferencia vienen el banco ("ENVIADO A" o
"RECIBIDO DE"), la cuenta, el beneficiario y la clave de rastreo. `spei()` los
entrega en el formato de `ceps.py`, para consultar cada CEP en Banxico.
"""

import re

from mifel import cuadra  # noqa: F401  (misma regla: cadena de saldos y totales)

RE_MONTO = re.compile(r"^[\d,]+\.\d{2}$")
RE_FECHA = re.compile(r"^(\d{2})-(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)-(\d{4})")
MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}

INICIO_TABLA = "Detalle de movimientos cuenta de cheques"


def _num(t):
    return float(t.replace(",", ""))


def _fecha(texto):
    m = RE_FECHA.match(texto)
    if not m:
        return None
    return "%s-%02d-%s" % (m.group(3), MESES[m.group(2)], m.group(1))


def _paginas(pdf):
    """Las páginas sin caracteres duplicados (ver el docstring del módulo)."""
    return [p.dedupe_chars() for p in pdf.pages]


# ─────────────────────────────────────────────────────────────────────────────
# Encabezado
# ─────────────────────────────────────────────────────────────────────────────
def encabezado(paginas):
    t0 = paginas[0].extract_text() or ""

    def buscar(patron, conv=_num):
        m = re.search(patron, t0)
        return conv(m.group(1)) if m else None

    periodo = re.search(r"PERIODO DEL (\S+) AL (\S+)", t0)
    titular = re.search(r"^(.+?)\s+CODIGO DE CLIENTE", t0, re.M)
    return {
        "banco": "Santander",
        "cuenta": buscar(r"CUENTA SANTANDER PYME\s+([\d-]+)\s+CUENTA CLABE",
                         lambda s: s.replace("-", "")),
        "clabe": buscar(r"CUENTA CLABE:\s*(\d{18})", str),
        "titular": titular.group(1).strip() if titular else None,
        "rfc": buscar(r"R\.F\.C\.\s+([A-ZÑ&0-9]{12,13})\b", str),
        "moneda": "MXN" if "MONEDA NACIONAL" in t0 else None,
        "fecha_inicial": _fecha(periodo.group(1)) if periodo else None,
        "fecha_final": _fecha(periodo.group(2)) if periodo else None,
        "saldo_promedio": buscar(r"Saldo promedio\s+([\d,]+\.\d{2})"),
        "saldo_inicial": buscar(r"Saldo inicial\s+([\d,]+\.\d{2})"),
        "saldo_final": buscar(r"Saldo final\s+([\d,]+\.\d{2})"),
        "monto_depositos": buscar(r"\+\s*Dep\S*sitos\s+([\d,]+\.\d{2})"),
        "monto_retiros": buscar(r"-\s*Retiros\s+([\d,]+\.\d{2})"),
        "numero_depositos": None,   # Santander no los declara; se cuentan al parsear.
        "numero_retiros": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Movimientos
# ─────────────────────────────────────────────────────────────────────────────
def _renglones(pagina, tolerancia=2.5):
    palabras = sorted(pagina.extract_words(), key=lambda w: (round(w["top"], 1), w["x0"]))
    grupos, actual, y = [], [], None
    for w in palabras:
        if y is None or abs(w["top"] - y) <= tolerancia:
            actual.append(w)
            y = w["top"] if y is None else y
        else:
            grupos.append(actual)
            actual, y = [w], w["top"]
    if actual:
        grupos.append(actual)
    return grupos


def _tabla(paginas):
    """Los renglones (como listas de palabras) de la tabla de la cuenta de cheques.

    Empieza en "Detalle de movimientos cuenta de cheques" y termina en su línea
    TOTAL. Lo que sigue —Dinero Creciente, el glosario— no es de esta cuenta.
    """
    dentro, fuera = False, []
    for p in paginas:
        for r in _renglones(p):
            texto = " ".join(w["text"] for w in r)
            if INICIO_TABLA in texto:
                dentro = True
                continue
            if not dentro:
                continue
            if texto.startswith("TOTAL "):
                return fuera, r
            fuera.append(r)
    return fuera, None


def movimientos(paginas):
    renglones, _ = _tabla(paginas)
    filas, corte, fin_saldo = [], None, None
    for r in renglones:
        textos = [w["text"] for w in r]
        if textos[:1] == ["FECHA"] and "DEPOSITO" in textos and "RETIRO" in textos:
            dep = next(w for w in r if w["text"] == "DEPOSITO")
            ret = next(w for w in r if w["text"] == "RETIRO")
            sal = next(w for w in r if w["text"] == "SALDO")
            corte = (dep["x1"] + ret["x0"]) / 2
            fin_saldo = sal["x1"] + 40
            continue
        if corte is None or not RE_FECHA.match(textos[0]):
            continue
        importes = [w for w in r if RE_MONTO.match(w["text"]) and w["x1"] <= fin_saldo]
        if len(importes) < 2:
            continue
        monto_w, saldo_w = importes[-2], importes[-1]
        filas.append({
            "fecha": _fecha(textos[0]),
            "descripcion": " ".join(textos),
            "monto": _num(monto_w["text"]),
            "saldo": _num(saldo_w["text"]),
            "tipo": "abono" if monto_w["x1"] <= corte else "cargo",
        })
    return filas


def _conteos(movs):
    return (sum(1 for m in movs if m["tipo"] == "abono"),
            sum(1 for m in movs if m["tipo"] == "cargo"))


# ─────────────────────────────────────────────────────────────────────────────
# SPEI, para el CEP de Banxico
# ─────────────────────────────────────────────────────────────────────────────
# La fecha y el folio a veces vienen pegados ("03-AGO-20264680363ABONO"): el
# espacio entre ellos es opcional.
RE_SPEI = re.compile(r"^(\d{2}-[A-Z]{3}-\d{4})\s*\d*(PAGO|ABONO) TRANSFERENCIA SPEI\b.*?"
                     r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$")


def spei(renglones, clabe_propia):
    """Los SPEI de la tabla, con su bloque de detalle ya interpretado.

    `renglones` es el texto de la tabla, una línea por renglón. Un renglón con
    fecha cierra el detalle del SPEI anterior.
    """
    fuera, actual = [], None
    for linea in renglones:
        linea = linea.strip()
        if RE_FECHA.match(linea):
            actual = None
            m = RE_SPEI.match(linea)
            if not m:
                continue
            enviado = m.group(2) == "PAGO"
            actual = {
                "fecha": _fecha(m.group(1)),
                "descripcion": linea,
                "tipo": "spei_enviado" if enviado else "spei_recibido",
                "monto": _num(m.group(3)),
                "saldo": _num(m.group(4)),
            }
            if not enviado:
                actual.update({"banco_receptor": "Santander",
                               "cuenta_beneficiaria": clabe_propia})
            else:
                actual["banco_emisor"] = "Santander"
            fuera.append(actual)
            continue
        if actual is None:
            continue
        if linea.startswith("ENVIADO A "):
            actual["institucion_receptora"] = linea[len("ENVIADO A "):].strip()
        elif linea.startswith("RECIBIDO DE "):
            banco = linea[len("RECIBIDO DE "):].strip()
            actual["institucion_ordenante"] = banco
            actual["banco_emisor"] = banco
        elif linea.startswith("A LA CUENTA "):
            actual["cuenta_beneficiaria"] = linea.split()[-1]
        elif linea.startswith("AL CLIENTE "):
            actual["beneficiario"] = re.sub(r"\s*\(\s*1\s*\)\s*$", "",
                                            linea[len("AL CLIENTE "):]).strip()
        elif linea.startswith("CLAVE DE RASTREO "):
            actual["clave_rastreo"] = linea[len("CLAVE DE RASTREO "):].strip()
    return fuera


def spei_de_pdf(ruta):
    """Los SPEI de un estado de cuenta de Santander, listos para `ceps.py`."""
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        paginas = _paginas(pdf)
        enc = encabezado(paginas)
        renglones, _ = _tabla(paginas)
    return spei([" ".join(w["text"] for w in r) for r in renglones], enc.get("clabe"))


def leer(ruta):
    """(encabezado, movimientos) de un estado de cuenta de Santander."""
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        paginas = _paginas(pdf)
        enc = encabezado(paginas)
        movs = movimientos(paginas)
    enc["numero_depositos"], enc["numero_retiros"] = _conteos(movs)
    return enc, movs
