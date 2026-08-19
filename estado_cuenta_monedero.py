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

import re

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
