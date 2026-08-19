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
"""

import glob
import os
import re

import pdfplumber

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
    cargos = []
    for t in tablas:
        if not t or len(t) < 4 or t[0][0] != "Identificador" or t[0][1] != "Fecha":
            continue
        datos = t[1]
        m = RE_FECHA_HORA.match(datos[1] or "")
        fecha, hora = (m.group(1), m.group(2)) if m else (datos[1], None)
        valor_importe = t[3]
        cargos.append({
            "identificador": datos[0],
            "fecha": fecha,
            "hora": hora,
            "rfc_estacion": datos[3],
            "clave_estacion": datos[4],
            "cantidad": float(datos[5]) if datos[5] else None,
            "tipo_combustible": datos[6],
            "nombre_combustible": datos[8],
            "folio_operacion": datos[9],
            "valor_unitario": float(valor_importe[0]) if valor_importe[0] else None,
            "importe": float(valor_importe[2]) if valor_importe[2] else None,
        })
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
        cargos = []
        for pagina in pdf.pages:
            tablas = pagina.extract_tables()
            if resumen is None:
                resumen = _resumen_cuenta(tablas)
            cargos.extend(_cargos(tablas))
    return {"encabezado": encabezado, "resumen": resumen, "cargos": cargos}


def _partes_nombre(nombre_archivo):
    """RFC_CLIENTE_RFC_MONEDERO_AAAA-MM.pdf -> (rfc_cliente, rfc_monedero,
    mes). El parser no depende de esto para leer el PDF —lee RFC y fechas
    del propio documento—; es solo para organizar la descarga manual."""
    nombre, ext = os.path.splitext(os.path.basename(nombre_archivo))
    if ext.lower() != ".pdf":
        return None
    partes = nombre.split("_")
    if len(partes) != 3:
        return None
    return tuple(partes)


def reporte_carpeta(carpeta):
    """Lee todos los PDF de una carpeta y arma el reporte final: por
    cliente, cada mes con su monedero, estaciones agregadas y total; y los
    PDF sospechosos (no cuadraron, o su nombre no sigue la convención) por
    separado, nunca mezclados en el agregado."""
    resultado = {}
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.pdf"))):
        partes = _partes_nombre(ruta)
        if partes is None:
            resultado.setdefault("_sin_clasificar", {"meses": {}, "sospechosos": []})
            resultado["_sin_clasificar"]["sospechosos"].append(ruta)
            continue
        rfc_cliente, rfc_monedero, mes = partes
        cliente = resultado.setdefault(rfc_cliente, {"meses": {}, "sospechosos": []})
        datos = leer_pdf(ruta)
        if not cuadra(datos["cargos"], datos["resumen"]):
            cliente["sospechosos"].append(ruta)
            continue
        cliente["meses"][(mes, rfc_monedero)] = {
            "rfc_monedero": rfc_monedero,
            "por_estacion": agregar_por_estacion(datos["cargos"]),
            "total": datos["resumen"]["subtotal"] if datos["resumen"] else None,
        }
    return resultado


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
            print("  %s  %-16s  $%s" % (
                mes, d["rfc_monedero"], format(d["total"] or 0, ",.2f")))
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
