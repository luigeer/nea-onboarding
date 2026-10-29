# -*- coding: utf-8 -*-
"""
bbva.py — Lee los estados de cuenta MAESTRA PYME de BBVA
=========================================================
El proyecto ya lee los de Banco del Bajío (`ceps.py`). Este es el segundo banco
y no comparte nada del formato, así que va aparte en vez de meterle ramas al
otro.

**Por qué por posición y no por texto.** En el detalle de movimientos, el monto
aparece en la columna de CARGOS o en la de ABONOS, y las dos se ven igual cuando
extraes el texto de la página: sale un número sin decir de qué columna venía.
Un cargo leído como abono convierte un pago en un depósito. Así que la dirección
se decide por la **coordenada horizontal** del número contra la x del encabezado
de cada columna, que es el único dato que la distingue.

**La comprobación que hace esto confiable.** La página 1 del estado trae el total
de depósitos y de retiros y cuántos movimientos son, calculados por el banco.
`cuadra()` compara lo que parseamos contra eso. Si no cuadra, no se guarda: un
estado de cuenta mal leído entra al modelo de riesgo como si fuera bueno y
nadie lo nota.

**La clasificación del depósito** sale del código de operación de BBVA, no de la
descripción. El código es un dato estructurado de tres caracteres; la
descripción es texto libre que cambia de un mes a otro. Esa lección ya se pagó
una vez, cuando "D E POSITO" con espacios dejó fuera 1,516 movimientos.
"""

import re

# Códigos de operación de BBVA que representan entrada de efectivo físico. Es la
# distinción que más importa para PLD: un depósito en efectivo no tiene
# ordenante identificable, un SPEI sí.
CODIGOS_EFECTIVO = {"C02", "AA7", "AA8", "C01"}
# Traspasos entre cuentas del propio titular: no son ingreso del negocio.
CODIGOS_PROPIAS = {"N03"}
# Abonos con contraparte identificable.
CODIGOS_SPEI = {"T20", "T09"}          # SPEI y TEF recibidos
CODIGOS_TERCERO = {"W02", "N06", "AP6", "C07"}
# Un SPEI devuelto es dinero que salió y regresó porque no se pudo entregar. El
# banco lo suma a los depósitos del periodo, pero NO es ingreso: contarlo como
# tal infla la entrada de dinero del negocio con su propio dinero rebotado.
CODIGOS_DEVOLUCION = {"T22"}

RE_MONTO = re.compile(r"^-?[\d,]+\.\d{2}$")
RE_FECHA = re.compile(r"^\d{2}/[A-Z]{3}$")
RE_CODIGO = re.compile(r"^[A-Z]\d{2}$|^[A-Z]{2}\d$")

MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}


def _num(t):
    return float(t.replace(",", ""))


def encabezado(pagina):
    """Los datos del bloque de resumen de la página 1, que declara el banco."""
    t = pagina.extract_text() or ""

    def buscar(patron, conv=_num):
        m = re.search(patron, t)
        return conv(m.group(1)) if m else None

    per = re.search(r"DEL (\d{2}/\d{2}/\d{4}) AL (\d{2}/\d{2}/\d{4})", t)
    dep = re.search(r"Depósitos / Abonos \(\+\)\s+(\d+)\s+([\d,]+\.\d{2})", t)
    ret = re.search(r"Retiros / Cargos \(-\)\s+(\d+)\s+([\d,]+\.\d{2})", t)

    def fecha(s):
        d, m, a = s.split("/")
        return "%s-%s-%s" % (a, m, d)

    return {
        "banco": "BBVA",
        "cuenta": buscar(r"No\. de Cuenta\s+(\d+)", str),
        "clabe": buscar(r"No\. Cuenta CLABE\s+(\d+)", str),
        "titular": buscar(r"^(.+?)\n.*Fecha de Corte", str) or None,
        "rfc": buscar(r"R\.F\.C\s+([A-Z0-9&Ñ]{12,13})", str),
        "moneda": "MXN",
        "fecha_inicial": fecha(per.group(1)) if per else None,
        "fecha_final": fecha(per.group(2)) if per else None,
        "saldo_promedio": buscar(r"Saldo Promedio\s+([\d,]+\.\d{2})"),
        "saldo_inicial": buscar(r"Saldo de Liquidación Inicial\s+([\d,]+\.\d{2})"),
        "saldo_final": buscar(r"Saldo Final \(\+\)\s+([\d,]+\.\d{2})"),
        "numero_depositos": int(dep.group(1)) if dep else None,
        "monto_depositos": _num(dep.group(2)) if dep else None,
        "numero_retiros": int(ret.group(1)) if ret else None,
        "monto_retiros": _num(ret.group(2)) if ret else None,
    }


def _columnas(pagina):
    """La x de cada columna de importes, leída de los encabezados de la página."""
    cols = {}
    for w in pagina.extract_words():
        if w["text"] in ("CARGOS", "ABONOS", "OPERACIÓN", "LIQUIDACIÓN"):
            cols.setdefault(w["text"], w["x1"])
    return cols


def movimientos(pdf):
    """Los movimientos del estado, con su dirección resuelta por posición.

    Un renglón de movimiento empieza con la fecha de operación; lo que sigue en
    renglones sin fecha son datos de la referencia del mismo movimiento. El
    importe se asigna a cargo o abono según en qué columna cayó.
    """
    filas = []
    for pagina in pdf.pages:
        cols = _columnas(pagina)
        if "CARGOS" not in cols or "ABONOS" not in cols:
            continue
        # Tolerancia: el número se alinea a la derecha, así que se compara su x1
        # contra la x1 del encabezado. La mitad de la distancia entre columnas
        # separa una de otra sin ambigüedad.
        corte = (cols["CARGOS"] + cols["ABONOS"]) / 2
        for palabras in _renglones(pagina):
            texto = " ".join(w["text"] for w in palabras)
            if not RE_FECHA.match(palabras[0]["text"]):
                continue
            codigo = next((w["text"] for w in palabras if RE_CODIGO.match(w["text"])), None)
            importes = [w for w in palabras if RE_MONTO.match(w["text"])]
            # Los saldos de OPERACIÓN y LIQUIDACIÓN también son importes: se
            # descartan por estar a la derecha de ABONOS.
            movs = [w for w in importes if w["x1"] <= cols["ABONOS"] + 6]
            if not movs:
                continue
            m = movs[0]
            filas.append({
                "fecha": palabras[0]["text"],
                "codigo": codigo,
                "descripcion": texto,
                "monto": _num(m["text"]),
                "tipo": "cargo" if m["x1"] <= corte else "abono",
            })
    return filas


def _renglones(pagina, tolerancia=2.5):
    """Agrupa las palabras de la página en renglones por su coordenada vertical."""
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


def clasificar(movs):
    """Agrupa los abonos por origen, usando el código de operación."""
    grupos = {"efectivo": [], "spei": [], "tercero": [], "cuentas_propias": [],
              "devoluciones": [], "otro": []}
    for m in movs:
        if m["tipo"] != "abono":
            continue
        c = m["codigo"]
        if c in CODIGOS_EFECTIVO:
            grupos["efectivo"].append(m)
        elif c in CODIGOS_SPEI:
            grupos["spei"].append(m)
        elif c in CODIGOS_TERCERO:
            grupos["tercero"].append(m)
        elif c in CODIGOS_PROPIAS:
            grupos["cuentas_propias"].append(m)
        elif c in CODIGOS_DEVOLUCION:
            grupos["devoluciones"].append(m)
        else:
            grupos["otro"].append(m)
    return {k: {"numero": len(v), "monto": round(sum(x["monto"] for x in v), 2)}
            for k, v in grupos.items()}


def cuadra(enc, movs, tolerancia=0.02):
    """¿Lo parseado coincide con lo que el banco declara en su resumen?

    Devuelve (bool, diagnóstico). Si no cuadra no se guarda nada: un estado de
    cuenta mal leído entra al modelo como si fuera bueno.
    """
    ab = [m for m in movs if m["tipo"] == "abono"]
    ca = [m for m in movs if m["tipo"] == "cargo"]
    d = {
        "depositos_monto": (round(sum(m["monto"] for m in ab), 2), enc["monto_depositos"]),
        "depositos_numero": (len(ab), enc["numero_depositos"]),
        "retiros_monto": (round(sum(m["monto"] for m in ca), 2), enc["monto_retiros"]),
        "retiros_numero": (len(ca), enc["numero_retiros"]),
    }
    ok = True
    for k, (mio, banco) in d.items():
        if banco is None:
            ok = False
        elif k.endswith("monto"):
            ok = ok and abs(mio - banco) <= tolerancia
        else:
            ok = ok and mio == banco
    return ok, d


def leer(ruta):
    """(encabezado, movimientos) de un estado de cuenta de BBVA."""
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        return encabezado(pdf.pages[0]), movimientos(pdf)


# ── SPEI para comprobar en Banxico ───────────────────────────────────────────
# BBVA no rotula el detalle del SPEI como Banco del Bajio (`ceps.py`, con
# "BENEFICIARIO:", "CLAVE DE RASTREO:", etc.): despues del renglon del
# movimiento vienen hasta cuatro renglones sin etiqueta -referencia y banco,
# cuenta de la contraparte, clave de rastreo, nombre- y el orden es lo unico
# que dice que es cada uno. Sin etiqueta que avise un error de lectura, un dato
# mal leido no se nota solo. Por eso cada candidato se valida por su forma
# -una cuenta son puros digitos, una clave de rastreo no tiene espacios- antes
# de aceptarlo; si no cuadra, el movimiento se devuelve con `revisar_manual`
# en vez de con un dato inventado.
RE_SPEI_HEADER = re.compile(
    r"^(\d{2}/[A-Z]{3})\s+\d{2}/[A-Z]{3}\s+(T17|T20)\s+SPEI\s*(ENVIADO|RECIBIDO)\s*"
    r"(.*?)\s+([\d,]+\.\d{2})(?:\s+[\d,]+\.\d{2}){0,2}\s*$")
# El inicio de CUALQUIER movimiento (no solo SPEI) marca el fin del bloque de
# detalle del anterior: así se sabe dónde parar aunque falten renglones.
RE_MOV_GENERICO = re.compile(r"^\d{2}/[A-Z]{3}\s+\d{2}/[A-Z]{3}\s+[A-Z0-9]{3}\b")
# Pie y encabezado que BBVA repite en cada pagina. Si un bloque de detalle cae
# justo en el salto de pagina, esto es lo que queda en medio; se filtra antes
# de leer el detalle para no confundirlo con la cuenta, la clave o el nombre.
RE_BOILERPLATE = re.compile(
    r"^(Estado de Cuenta|MAESTRA PYME BBVA|PAGINA \d+ */ *\d+|No\. Cuenta|"
    r"No\. Cliente|FECHA SALDO|OPER LIQ COD|BBVA MEXICO|"
    r"Av\. Paseo de la Reforma|Total de Movimientos)")
RE_REF_BANCO = re.compile(r"Ref\.\s*(\S+)(?:\s+(\d{3}))?\s*$")
RE_CUENTA_CONTRAPARTE = re.compile(r"^\d{10,20}$")
RE_CLAVE_RASTREO = re.compile(r"^[A-Z0-9][A-Z0-9\-/]{9,29}$")


def _bloques_spei(renglones, anio):
    """Los SPEI enviados y recibidos, con su detalle para comprobar en Banxico.

    Solo T17 (SPEI ENVIADO) y T20 (SPEI RECIBIDO) traen el bloque de detalle.
    T09 (TEF RECIBIDO) es un sistema distinto -Banxico solo emite CEP de
    SPEI- y no lo trae, así que no aparece en el resultado.
    """
    limpios = [r for r in renglones if not RE_BOILERPLATE.match(r.strip())]

    fuera = []
    i = 0
    while i < len(limpios):
        m = RE_SPEI_HEADER.match(limpios[i])
        if not m:
            i += 1
            continue
        fecha_txt, codigo, direccion, banco, monto_txt = m.groups()
        dia, mes = fecha_txt.split("/")
        mov = {
            "fecha": "%s-%02d-%02d" % (anio, MESES[mes], int(dia)),
            "codigo": codigo,
            "tipo": "spei_enviado" if direccion == "ENVIADO" else "spei_recibido",
            "banco_contraparte": banco.strip() or None,
            "monto": _num(monto_txt),
            "referencia": None,
            "cuenta_contraparte": None,
            "clave_rastreo": None,
            "contraparte": None,
            "revisar_manual": True,
        }

        siguientes = []
        j = i + 1
        while (j < len(limpios) and len(siguientes) < 5
               and not RE_MOV_GENERICO.match(limpios[j])):
            siguientes.append(limpios[j])
            j += 1

        if siguientes:
            ref = RE_REF_BANCO.search(siguientes[0])
            if ref:
                mov["referencia"] = ref.group(1)

        if len(siguientes) >= 3:
            cuenta, clave = siguientes[1].strip(), siguientes[2].strip()
            if RE_CUENTA_CONTRAPARTE.match(cuenta) and RE_CLAVE_RASTREO.match(clave):
                mov["cuenta_contraparte"] = cuenta
                mov["clave_rastreo"] = clave
                mov["contraparte"] = siguientes[3].strip() if len(siguientes) > 3 else None
                mov["revisar_manual"] = False

        # Forma alterna: "pago a tercero" sin cuenta beneficiaria propia. El
        # concepto ("COMPRA VENTA DE DOCUMENTOS") no cupo en el renglon de
        # referencia y el codigo de banco quedo suelto en el siguiente; donde
        # iria la cuenta aparece el literal "BANCO A TERCERO" en vez de una
        # CLABE, y la clave de rastreo se recorre un renglon.
        if mov["revisar_manual"] and len(siguientes) >= 4:
            banco_solo, marca, clave = (siguientes[1].strip(), siguientes[2].strip(),
                                         siguientes[3].strip())
            if (re.match(r"^\d{3}$", banco_solo) and marca.upper() == "BANCO A TERCERO"
                    and RE_CLAVE_RASTREO.match(clave)):
                mov["clave_rastreo"] = clave
                mov["contraparte"] = siguientes[4].strip() if len(siguientes) > 4 else marca
                mov["revisar_manual"] = False

        fuera.append(mov)
        i += 1
    return fuera


def leer_spei(ruta, anio):
    """Los SPEI de un estado de cuenta de BBVA, con su detalle para Banxico."""
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        renglones = []
        for pagina in pdf.pages:
            renglones.extend((pagina.extract_text() or "").split("\n"))
    return _bloques_spei(renglones, anio)
