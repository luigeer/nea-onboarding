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
