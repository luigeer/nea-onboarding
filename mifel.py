# -*- coding: utf-8 -*-
"""
mifel.py — Lee los estados de cuenta CUENTA A LA VISTA de Banca Mifel
=======================================================================
Tercer banco después de BBVA (`bbva.py`). El formato no comparte nada con
BBVA: no hay códigos de operación de tres caracteres, solo una columna de
Retiros, una de Depósitos y una de Saldo corrido.

**Por qué por posición y no por texto.** Igual que en BBVA: el importe de un
movimiento aparece en la columna de Retiros o en la de Depósitos, y las dos se
ven idénticas en el texto extraído del PDF. La dirección se decide comparando
la coordenada horizontal del número contra el punto medio entre las dos
columnas, que es el único dato que las distingue.

**La comprobación que hace esto confiable.** Mifel no publica cuántos
movimientos hubo —a diferencia de BBVA, que sí declara depósitos y retiros
por número—, pero sí publica el saldo después de cada movimiento. `cuadra()`
reconstruye el saldo corrido a partir del saldo inicial y cada movimiento
parseado, y lo compara renglón por renglón contra el saldo que el propio
estado de cuenta declaró en ese renglón: un movimiento leído en la dirección
equivocada rompe la cadena en ese momento exacto, no solo al final. También
se compara la suma de depósitos y de retiros contra la línea "Suma de retiros
y depósitos" que trae el estado, como segunda verificación independiente.
"""

import re

RE_MONTO = re.compile(r"^-?[\d,]+\.\d{2}$")
RE_FECHA = re.compile(r"^\d{2}/\d{2}/\d{4}$")

TOLERANCIA = 0.01


def _num(t):
    return float(t.replace(",", ""))


def _fecha(s):
    d, m, a = s.split("/")
    return "%s-%s-%s" % (a, m, d)


# ─────────────────────────────────────────────────────────────────────────────
# Encabezado
# ─────────────────────────────────────────────────────────────────────────────
def _paginas_detalle(pdf):
    """Las páginas que contienen la tabla 'Detalles de la Cuenta a la vista'.

    Empieza en la página donde aparece ese título y termina en la página
    donde aparece 'Suma de retiros y depósitos', que es el cierre de la
    tabla. El resto del PDF (fondos de inversión, glosario, comprobante
    fiscal) no son movimientos de la cuenta a la vista.
    """
    textos = [p.extract_text() or "" for p in pdf.pages]
    inicio = next((i for i, t in enumerate(textos)
                   if "Detalles de la Cuenta a la vista" in t), None)
    if inicio is None:
        return []
    fin = next((i for i in range(inicio, len(textos))
               if "Suma de retiros y dep" in textos[i]), len(textos) - 1)
    return list(range(inicio, fin + 1))


def encabezado(pdf):
    """Los datos generales del estado de cuenta, tomados de varias páginas."""
    t0 = pdf.pages[0].extract_text() or ""

    def buscar(patron, texto, conv=_num):
        m = re.search(patron, texto)
        return conv(m.group(1)) if m else None

    periodo = re.search(r"Periodo DEL (\d{2}/\d{2}/\d{4}) AL (\d{2}/\d{2}/\d{4})", t0)
    titular = re.search(r"^(.+?)\s+Informaci[oó]n del cliente", t0, re.M)

    paginas = _paginas_detalle(pdf)
    t_ini = (pdf.pages[paginas[0]].extract_text() or "") if paginas else ""
    t_fin = (pdf.pages[paginas[-1]].extract_text() or "") if paginas else ""

    suma = re.search(r"Suma de retiros y dep[oó]sitos\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
                     t_fin)
    saldo_corte = buscar(r"Saldo a fecha de corte\s+([\d,]+\.\d{2})", t_fin)

    return {
        "banco": "Mifel",
        "cuenta": buscar(r"N[uú]mero de cuenta\s+(\d+)", t0, str),
        "clabe": buscar(r"CLABE\s+(\d+)", t0, str),
        "titular": titular.group(1).strip() if titular else None,
        "rfc": buscar(r"\bRFC\s+([A-ZÑ&0-9]{12,13})\b", t0, str),
        "moneda": "MXN",
        "fecha_inicial": _fecha(periodo.group(1)) if periodo else None,
        "fecha_final": _fecha(periodo.group(2)) if periodo else None,
        "saldo_promedio": buscar(r"Saldo promedio diario\s+([\d,]+\.\d{2})", t0),
        "saldo_inicial": buscar(r"Saldo inicial\s+([\d,]+\.\d{2})", t_ini),
        "saldo_final": saldo_corte,
        "monto_retiros": _num(suma.group(1)) if suma else None,
        "monto_depositos": _num(suma.group(2)) if suma else None,
        "numero_depositos": None,   # Mifel no declara un conteo; se cuenta al parsear.
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


def _columnas(pdf, paginas):
    """La x de Retiros/Depósitos/Saldo, leída del renglón de encabezado.

    Ese renglón solo aparece una vez, en la primera página de la tabla; las
    páginas siguientes traen puros movimientos, sin repetir el encabezado.
    """
    for i in paginas:
        palabras = pdf.pages[i].extract_words()
        fecha = next((w for w in palabras if w["text"] == "Fecha"), None)
        if not fecha:
            continue
        fila = [w for w in palabras if abs(w["top"] - fecha["top"]) <= 1.0]
        cols = {w["text"]: (w["x0"], w["x1"]) for w in fila
                if w["text"] in ("Retiros", "Depósitos", "Saldo")}
        if "Retiros" in cols and "Depósitos" in cols and "Saldo" in cols:
            return cols
    return {}


def movimientos(pdf):
    """Los movimientos de la cuenta a la vista, con su saldo corrido.

    Un renglón de movimiento empieza con una fecha dd/mm/aaaa; lo que sigue
    en renglones sin fecha son continuaciones de la descripción del mismo
    movimiento (Mifel corta el texto de "TRANSFERENCIA SPEI ... - RTGS" a la
    mitad cuando no cabe en una línea).
    """
    paginas = _paginas_detalle(pdf)
    cols = _columnas(pdf, paginas)
    if not cols:
        return []

    corte = (cols["Retiros"][1] + cols["Depósitos"][0]) / 2
    fin_saldo = cols["Saldo"][1] + 40   # el saldo se ensancha con números grandes

    filas = []
    for i in paginas:
        for palabras in _renglones(pdf.pages[i]):
            if not RE_FECHA.match(palabras[0]["text"]):
                continue
            texto = " ".join(w["text"] for w in palabras)
            importes = [w for w in palabras if RE_MONTO.match(w["text"])]
            # El saldo corrido es el importe más a la derecha; el monto del
            # movimiento es el que queda antes de él.
            importes = [w for w in importes if w["x1"] <= fin_saldo]
            if len(importes) < 2:
                continue
            saldo_w = importes[-1]
            monto_w = importes[-2]
            filas.append({
                "fecha": palabras[0]["text"],
                "descripcion": texto,
                "monto": _num(monto_w["text"]),
                "saldo": _num(saldo_w["text"]),
                "tipo": "cargo" if monto_w["x1"] <= corte else "abono",
            })
    return filas


# ─────────────────────────────────────────────────────────────────────────────
# Cuadre
# ─────────────────────────────────────────────────────────────────────────────
def cuadra(enc, movs, tolerancia=TOLERANCIA):
    """¿La cadena de saldos y los totales cuadran contra lo que declara Mifel?

    Devuelve (bool, diagnóstico). Reconstruye el saldo corrido desde
    saldo_inicial aplicando cada movimiento en orden, y lo compara contra el
    saldo que ese mismo renglón trae impreso: un solo movimiento mal
    clasificado rompe la cadena ahí mismo, no hasta el final.
    """
    diagnostico = {}

    if not movs:
        return False, {"error": "sin movimientos que reconciliar"}

    saldo_inicial = enc.get("saldo_inicial")
    saldo_final_declarado = enc.get("saldo_final")
    if saldo_inicial is None or saldo_final_declarado is None:
        return False, {"error": "encabezado sin saldo inicial o final"}

    saldo = saldo_inicial
    for idx, m in enumerate(movs):
        saldo = saldo - m["monto"] if m["tipo"] == "cargo" else saldo + m["monto"]
        if abs(saldo - m["saldo"]) > tolerancia:
            diagnostico["renglon_roto"] = {
                "indice": idx, "esperado": round(saldo, 2), "declarado": m["saldo"]}
            return False, diagnostico

    diagnostico["saldo_final"] = (round(saldo, 2), saldo_final_declarado)
    if abs(saldo - saldo_final_declarado) > tolerancia:
        return False, diagnostico

    depositos = round(sum(m["monto"] for m in movs if m["tipo"] == "abono"), 2)
    retiros = round(sum(m["monto"] for m in movs if m["tipo"] == "cargo"), 2)
    diagnostico["depositos"] = (depositos, enc.get("monto_depositos"))
    diagnostico["retiros"] = (retiros, enc.get("monto_retiros"))

    if enc.get("monto_depositos") is not None and abs(depositos - enc["monto_depositos"]) > tolerancia:
        return False, diagnostico
    if enc.get("monto_retiros") is not None and abs(retiros - enc["monto_retiros"]) > tolerancia:
        return False, diagnostico

    return True, diagnostico


def _conteos(movs):
    """(número de depósitos, número de retiros). Mifel no los declara, a
    diferencia de BBVA ("Depósitos/Abonos (+) N monto"), así que se cuentan
    de lo que se parseó."""
    depositos = sum(1 for m in movs if m["tipo"] == "abono")
    retiros = sum(1 for m in movs if m["tipo"] == "cargo")
    return depositos, retiros


def leer(ruta):
    """(encabezado, movimientos) de un estado de cuenta de Mifel."""
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        movs = movimientos(pdf)
        enc = encabezado(pdf)
    enc["numero_depositos"], enc["numero_retiros"] = _conteos(movs)
    return enc, movs
