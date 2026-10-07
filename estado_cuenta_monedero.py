# -*- coding: utf-8 -*-
"""
estado_cuenta_monedero.py — El complemento de combustible, de PDF a datos
============================================================================
Ver el diseño completo en
docs/superpowers/specs/2026-08-19-estaciones-monedero-design.md.

"Estado de Cuenta de Combustibles para Monederos Electrónicos" es un
complemento estandarizado por el SAT: la misma estructura de tablas sin
importar qué monedero lo emite (se confirmó comparando un PDF de Efecticard
y uno de Sí Vale — columnas idénticas). Por eso un solo parser sirve para
todos, y no hace falta uno por monedero.

**Por qué extract_tables() y no extract_text().** El PDF usa celdas de
tabla sin espacio entre ellas; `extract_text()` pega las palabras
("ClavedeEstación", "RFCemisor") y vuelve ambiguo separar campos que a su
vez tienen texto libre. `extract_tables()` respeta el límite de cada
celda. El encabezado (RFC emisor/receptor, folio fiscal) es la excepción:
esas etiquetas sí van en texto corrido, no en una tabla con bordes, así que
se leen con regex sobre extract_text() de la primera página.

**Por qué se cuadra contra el subtotal declarado.** El resumen de cuenta
("Versión / Tipo de Operación / Número de Cuenta / Subtotal / Total") lo
calcula el propio monedero. Si la suma de los cargos que se lograron
parsear no coincide, algo se leyó mal o incompleto — un PDF así se marca
sospechoso en vez de usarse a medias, mismo principio que ya usa
`bbva.cuadra()` para los estados de cuenta bancarios.
**Por qué también se lee el XML, no solo el PDF.** El XML es el CFDI
crudo: el mismo complemento, pero como atributos con nombre en vez de
celdas de tabla. Sin la ambigüedad de `extract_tables()` ni el riesgo de
un índice equivocado — se confirmó a mano contra un XML real que la suma
de importes cuadra exacto contra el subtotal declarado. Si el panel de
Syntage da a elegir, XML es preferible al PDF por esto mismo.
"""

import glob
import os
import re
import xml.etree.ElementTree as ET

import pdfplumber

_NS_XML = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "ecc12": "http://www.sat.gob.mx/EstadoDeCuentaCombustible12",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}

RE_RFC_EMISOR = re.compile(r"RFCemisor:\s*(\S+)")
RE_RFC_RECEPTOR = re.compile(r"RFCreceptor:\s*(\S+)")
RE_FOLIO_FISCAL = re.compile(r"Foliofiscal:\s*(\S+)")
RE_FECHA_HORA = re.compile(r"^(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})$")


def _encabezado(texto_pagina1):
    """RFC emisor/receptor y folio fiscal: vienen en texto corrido de la
    página 1, no en una tabla con bordes."""
    e = RE_RFC_EMISOR.search(texto_pagina1)
    r = RE_RFC_RECEPTOR.search(texto_pagina1)
    f = RE_FOLIO_FISCAL.search(texto_pagina1)
    return {
        "rfc_emisor": e.group(1) if e else None,
        "rfc_receptor": r.group(1) if r else None,
        "folio_fiscal": f.group(1) if f else None,
    }


def _resumen_cuenta(tablas):
    """La tabla 'Versión / Tipo de Operación / Número de Cuenta / Subtotal /
    Total'. No siempre está en la misma página que los cargos, así que se
    busca en vez de asumir su posición."""
    for t in tablas:
        if t and t[0][:1] == ["Versión"]:
            fila = t[1]
            return {
                "version": fila[0],
                "tipo_operacion": fila[1],
                "numero_cuenta": fila[2],
                "subtotal": float(fila[3]),
                "total": float(fila[4]),
            }
    return None


def _cargos(tablas):
    """Cada bloque de cargo es una tabla de 4 filas: encabezado, datos,
    encabezado de 'Valor Unitario/Importe', datos de esos dos. Se
    distingue de la tabla de 'Traslados' (que también tiene forma de
    tabla chica) por su propio encabezado ('Identificador', 'Fecha')."""
    # Las columnas se leen por el nombre de su encabezado, no por posición:
    # según dónde cae en la hoja, la tabla trae o no una columna vacía entre
    # Fecha y RFC, y leer por posición tomaba la clave como RFC.
    #
    # Un cargo al pie de página queda partido: el encabezado y los datos en
    # una página, y el valor unitario e importe al inicio de la siguiente,
    # bajo el encabezado repetido. Por eso se reciben las tablas de todas
    # las páginas en orden, y un cargo sin importe se completa con la
    # siguiente tabla de cargo que solo traiga esas filas. Antes se perdía el
    # cargo completo y el estado no cuadraba por exactamente ese importe.
    def _num(v):
        return float(v) if v else None

    cargos, pendiente = [], None
    for t in tablas:
        if not t or not t[0] or t[0][0] != "Identificador" or "Fecha" not in t[0]:
            continue
        col = {nombre: i for i, nombre in enumerate(t[0]) if nombre}
        filas = t[1:]
        datos = filas[0] if filas and filas[0] and filas[0][0] != "ValorUnitario" else None
        vu_i = next((i for i, f in enumerate(filas) if f and f[0] == "ValorUnitario"), None)
        valor_importe = None
        if vu_i is not None and vu_i + 1 < len(filas):
            cab, val = filas[vu_i], filas[vu_i + 1]
            pos = {nombre: i for i, nombre in enumerate(cab) if nombre}
            valor_importe = (val[pos["ValorUnitario"]], val[pos.get("Importe", 2)])

        if datos is None:
            if pendiente is not None and valor_importe:
                pendiente["valor_unitario"] = _num(valor_importe[0])
                pendiente["importe"] = _num(valor_importe[1])
                cargos.append(pendiente)
                pendiente = None
            continue

        dato = lambda nombre: datos[col[nombre]] if nombre in col else None
        m = RE_FECHA_HORA.match(dato("Fecha") or "")
        fecha, hora = (m.group(1), m.group(2)) if m else (dato("Fecha"), None)
        cargo = {
            "identificador": dato("Identificador"),
            "fecha": fecha,
            "hora": hora,
            "rfc_estacion": dato("RFC"),
            "clave_estacion": dato("ClavedeEstación"),
            "cantidad": _num(dato("Cantidad")),
            "tipo_combustible": dato("TipodeCombustible"),
            "nombre_combustible": dato("NombreCombustible"),
            "folio_operacion": dato("FoliodeOperación"),
            "valor_unitario": _num(valor_importe[0]) if valor_importe else None,
            "importe": _num(valor_importe[1]) if valor_importe else None,
        }
        if valor_importe:
            cargos.append(cargo)
        else:
            pendiente = cargo
    return cargos


def cuadra(cargos, resumen, tolerancia=0.05):
    """La suma de importes debe coincidir con el subtotal que declaró el
    propio monedero. Si no cuadra, el PDF se marca sospechoso — nunca se
    usa a medias."""
    if resumen is None:
        return False
    suma = sum(c["importe"] or 0 for c in cargos)
    return abs(suma - resumen["subtotal"]) <= tolerancia


def agregar_por_estacion(cargos):
    """(RFC de estación, clave de estación) -> número de cargas, litros e
    importe total. La clave es el par, no solo la clave de estación: dos
    monederos distintos podrían coincidir en la clave interna."""
    agregado = {}
    for c in cargos:
        clave = (c["rfc_estacion"], c["clave_estacion"])
        a = agregado.setdefault(clave, {"cargas": 0, "litros": 0.0, "importe": 0.0})
        a["cargas"] += 1
        a["litros"] += c["cantidad"] or 0
        a["importe"] += c["importe"] or 0
    return agregado


def leer_pdf(ruta):
    """Todo lo que trae un PDF de complemento: encabezado, resumen de
    cuenta y cargos, juntando todas sus páginas. El resumen de cuenta se
    busca en cada página hasta encontrarlo porque no siempre está en la
    primera."""
    with pdfplumber.open(ruta) as pdf:
        encabezado = _encabezado(pdf.pages[0].extract_text() or "")
        resumen = None
        todas = []
        for pagina in pdf.pages:
            tablas = pagina.extract_tables()
            if resumen is None:
                resumen = _resumen_cuenta(tablas)
            todas.extend(tablas)
        # Todas las páginas juntas: un cargo puede quedar partido entre dos.
        cargos = _cargos(todas)
    return {"encabezado": encabezado, "resumen": resumen, "cargos": cargos}


def _parsear_complemento(raiz):
    """Todo lo que trae el CFDI en XML: encabezado, resumen de cuenta y
    cargos, leídos de sus atributos con nombre en vez de adivinar
    columnas de una tabla. El folio fiscal es el UUID del sello del SAT
    (TimbreFiscalDigital), no un dato del complemento en sí."""
    emisor = raiz.find("cfdi:Emisor", _NS_XML)
    receptor = raiz.find("cfdi:Receptor", _NS_XML)
    timbre = raiz.find(".//tfd:TimbreFiscalDigital", _NS_XML)
    encabezado = {
        "rfc_emisor": emisor.get("Rfc") if emisor is not None else None,
        "rfc_receptor": receptor.get("Rfc") if receptor is not None else None,
        "folio_fiscal": timbre.get("UUID") if timbre is not None else None,
    }

    ecc = raiz.find(".//ecc12:EstadoDeCuentaCombustible", _NS_XML)
    resumen = None
    if ecc is not None:
        resumen = {
            "version": ecc.get("Version"),
            "tipo_operacion": ecc.get("TipoOperacion"),
            "numero_cuenta": ecc.get("NumeroDeCuenta"),
            "subtotal": float(ecc.get("SubTotal")),
            "total": float(ecc.get("Total")),
        }

    cargos = []
    for c in raiz.findall(".//ecc12:ConceptoEstadoDeCuentaCombustible", _NS_XML):
        fecha_hora = c.get("Fecha") or ""
        fecha, _, hora = fecha_hora.partition("T")
        cargos.append({
            "identificador": c.get("Identificador"),
            "fecha": fecha or None,
            "hora": hora or None,
            "rfc_estacion": c.get("Rfc"),
            "clave_estacion": c.get("ClaveEstacion"),
            "cantidad": float(c.get("Cantidad")) if c.get("Cantidad") else None,
            "tipo_combustible": c.get("TipoCombustible"),
            "nombre_combustible": c.get("NombreCombustible"),
            "folio_operacion": c.get("FolioOperacion"),
            "valor_unitario": float(c.get("ValorUnitario")) if c.get("ValorUnitario") else None,
            "importe": float(c.get("Importe")) if c.get("Importe") else None,
        })

    return {"encabezado": encabezado, "resumen": resumen, "cargos": cargos}


def leer_xml(ruta):
    """El complemento leído directamente del CFDI en XML."""
    return _parsear_complemento(ET.parse(ruta).getroot())


def _partes_nombre(nombre_archivo):
    """RFC_CLIENTE_RFC_MONEDERO_AAAA-MM.pdf (o .xml) -> (rfc_cliente,
    rfc_monedero, mes). El parser no depende de esto para leer el
    archivo —lee RFC y fechas del propio documento—; es solo para
    organizar la descarga manual."""
    nombre, ext = os.path.splitext(os.path.basename(nombre_archivo))
    if ext.lower() not in (".pdf", ".xml"):
        return None
    # Un cuarto pedazo es el folio fiscal abreviado: lo lleva el nombre cuando
    # el mes tiene más de una factura (estaciones_monedero.archivos_unicos).
    partes = nombre.split("_")
    if len(partes) not in (3, 4):
        return None
    return tuple(partes[:3])


def reporte_carpeta(carpeta):
    """Lee todos los PDF/XML de una carpeta y arma el reporte final: por
    cliente, cada mes con su monedero, estaciones agregadas y subtotal; y
    los archivos sospechosos (no cuadraron, su nombre no sigue la
    convención, su propio RFC no coincide con el del archivo, o no se
    pudieron leer) por separado, nunca mezclados en el agregado.

    XML es preferible cuando el panel de Syntage lo permite (el CFDI
    crudo, sin la ambigüedad de extraer tablas de un PDF); PDF sigue
    soportado para lo que ya se haya bajado así.

    Estos archivos llegan de un flujo manual: se descargan del panel de
    Syntage (nombrados por UUID) y una persona los renombra a mano
    siguiendo la convención RFC_CLIENTE_RFC_MONEDERO_AAAA-MM.{pdf,xml}. Un
    archivo malformado o un desliz en ese renombrado no debe tumbar el
    resto del lote ni mezclar el gasto de un cliente con el de otro en
    silencio — "se marca sospechoso en vez de usarse a medias"."""
    resultado = {}
    rutas = sorted(glob.glob(os.path.join(carpeta, "*.pdf")) +
                   glob.glob(os.path.join(carpeta, "*.xml")))
    for ruta in rutas:
        partes = _partes_nombre(ruta)
        if partes is None:
            resultado.setdefault("_sin_clasificar", {"meses": {}, "sospechosos": []})
            resultado["_sin_clasificar"]["sospechosos"].append(ruta)
            continue
        rfc_cliente, rfc_monedero, mes = partes
        cliente = resultado.setdefault(rfc_cliente, {"meses": {}, "sospechosos": []})
        try:
            leer = leer_xml if ruta.lower().endswith(".xml") else leer_pdf
            datos = leer(ruta)
            encabezado = datos["encabezado"]
            # El PDF trae su propia identidad (RFC emisor/receptor) leída
            # del contenido, no del nombre del archivo. Si no coincide con
            # lo que dice el nombre, un renombrado a mano se equivocó de
            # cliente o de monedero: no se puede confiar en el nombre solo.
            if (encabezado["rfc_receptor"] != rfc_cliente
                    or encabezado["rfc_emisor"] != rfc_monedero):
                cliente["sospechosos"].append(
                    "%s (el PDF dice emisor=%s receptor=%s; el nombre de "
                    "archivo dice monedero=%s cliente=%s)" % (
                        ruta, encabezado["rfc_emisor"], encabezado["rfc_receptor"],
                        rfc_monedero, rfc_cliente))
                continue
            if not cuadra(datos["cargos"], datos["resumen"]):
                cliente["sospechosos"].append(ruta)
                continue
        except Exception as e:
            cliente["sospechosos"].append("%s (no se pudo leer: %s)" % (ruta, e))
            continue
        # Dos facturas del mismo mes y monedero se suman: antes la segunda
        # reemplazaba a la primera y el gasto del mes salía incompleto.
        previo = cliente["meses"].get((mes, rfc_monedero))
        por_estacion = agregar_por_estacion(datos["cargos"])
        subtotal = datos["resumen"]["subtotal"]
        if previo:
            for clave, a in previo["por_estacion"].items():
                b = por_estacion.setdefault(clave, {"cargas": 0, "litros": 0.0, "importe": 0.0})
                b["cargas"] += a["cargas"]
                b["litros"] += a["litros"]
                b["importe"] += a["importe"]
            subtotal = (previo["subtotal"] or 0) + (subtotal or 0)
        cliente["meses"][(mes, rfc_monedero)] = {
            "rfc_monedero": rfc_monedero,
            "por_estacion": por_estacion,
            "subtotal": subtotal,
        }
    return resultado


def reporte_cliente(rfc_cliente, carpeta="descargas/monederos"):
    """reporte_carpeta() filtrado a un solo cliente. No decide nada de
    comisión: eso ya lo tiene Etapa 1 (estaciones_monedero.revisar_cliente)."""
    reporte = reporte_carpeta(carpeta)
    return reporte.get(rfc_cliente, {"meses": {}, "sospechosos": []})


def main(argv):
    if len(argv) < 3 or argv[1] != "reporte":
        print("Uso: python estado_cuenta_monedero.py reporte <carpeta>")
        return 1

    reporte = reporte_carpeta(argv[2])
    for rfc_cliente, datos in reporte.items():
        if rfc_cliente == "_sin_clasificar":
            continue
        print("\n%s" % rfc_cliente)
        estaciones_totales = set()
        for (mes, _rfc_monedero), d in sorted(datos["meses"].items()):
            estaciones_totales.update(d["por_estacion"].keys())
            # "subtotal": es el monto antes de IVA que declara el propio
            # monedero; el "total" (con IVA, ~16% más alto) vive en
            # datos["resumen"] pero no se usa aquí — quien lea este reporte
            # para un análisis de riesgo crediticio necesita saber cuál es.
            print("  %s  %-16s  subtotal $%s (antes de IVA)" % (
                mes, d["rfc_monedero"], format(d["subtotal"] or 0, ",.2f")))
            for (rfc_est, clave_est), agregado in d["por_estacion"].items():
                print("      estacion %s/%s: %d carga(s), $%s" % (
                    rfc_est, clave_est, agregado["cargas"],
                    format(agregado["importe"], ",.2f")))
        print("  -> %d estacion(es) distinta(s) en los meses con PDF" % len(estaciones_totales))
        if datos["sospechosos"]:
            print("  ATENCION: %d PDF no cuadraron o no se pudieron usar:" % len(datos["sospechosos"]))
            for s in datos["sospechosos"]:
                print("    %s" % s)
    if reporte.get("_sin_clasificar", {}).get("sospechosos"):
        print("\nArchivos que no siguen la convención de nombre:")
        for s in reporte["_sin_clasificar"]["sospechosos"]:
            print("  %s" % s)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
