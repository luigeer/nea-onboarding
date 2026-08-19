# -*- coding: utf-8 -*-
"""
Pruebas de estado_cuenta_monedero.py.

El texto y las tablas de prueba son inventados, pero con la misma forma
exacta que produce pdfplumber sobre un PDF real de este complemento (se
confirmó a mano contra un PDF de ejemplo real, que no se sube al repo por
traer RFC y razón social de un cliente).

Se corre con:
    python tests/test_estado_cuenta_monedero.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estado_cuenta_monedero as ecm

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── _encabezado(): texto de pdfplumber, etiquetas de dos palabras pegadas ──
TEXTO_PAGINA1 = (
    "RFCemisor: FIC010101AB1 Foliofiscal: 11111111-2222-3333-4444-555555555555\n"
    "Nombreemisor: FICTICIAWALLET No.deseriedelCSD: 00001000000000000000\n"
    "Folio: 1\n"
    "RFCreceptor: CLI020202CD2 Codigopostal,fechayhorade 06600 2026-04-0122:22:37\n"
    "Nombrereceptor: CLIENTEDEPRUEBA emision:\n"
)

enc = ecm._encabezado(TEXTO_PAGINA1)
check(enc["rfc_emisor"] == "FIC010101AB1", "RFC emisor: %r" % enc["rfc_emisor"])
check(enc["rfc_receptor"] == "CLI020202CD2", "RFC receptor: %r" % enc["rfc_receptor"])
check(enc["folio_fiscal"] == "11111111-2222-3333-4444-555555555555",
      "folio fiscal (UUID): %r" % enc["folio_fiscal"])

enc_vacio = ecm._encabezado("texto sin ninguna de las etiquetas esperadas")
check(enc_vacio == {"rfc_emisor": None, "rfc_receptor": None, "folio_fiscal": None},
      "un texto sin las etiquetas no truena, regresa Nones")


# ── _resumen_cuenta(): la tabla resumen del estado de cuenta ───────────────
TABLA_RESUMEN = [
    ["Versión", "TipodeOperación", "NúmerodeCuenta", "Subtotal", "Total"],
    ["1.2", "Tarjeta", "F116300001", "50863.30", "58770.30"],
]
TABLA_NO_RESUMEN = [["Identificador", "Fecha"], ["dato", "dato"]]

resumen = ecm._resumen_cuenta([TABLA_NO_RESUMEN, TABLA_RESUMEN])
check(resumen is not None, "encuentra la tabla resumen aunque no sea la primera")
check(resumen["numero_cuenta"] == "F116300001", "número de cuenta: %r" % resumen["numero_cuenta"])
check(resumen["subtotal"] == 50863.30 and resumen["total"] == 58770.30,
      "subtotal y total salen como float: %r / %r" % (resumen["subtotal"], resumen["total"]))

check(ecm._resumen_cuenta([TABLA_NO_RESUMEN]) is None,
      "sin tabla resumen en esta página, regresa None (no truena)")


# ── _cargos(): cada bloque de cargo es una tabla de 4 filas ────────────────
# Forma real confirmada con pdfplumber.extract_tables() contra un PDF de
# ejemplo (RFC y clave de estación cambiados aquí a valores inventados).
TABLA_CARGO = [
    ["Identificador", "Fecha", None, "RFC", "ClavedeEstación", "Cantidad",
     "TipodeCombustible", "Unidad", "NombreCombustible", "FoliodeOperación"],
    ["XXXXXXXXXXXX\n0001", "2026-03-0919:06:04", None, "FIC120327XYZ", "9999999",
     "44.164", "1", "LTS", "GasolinaMagnaFleet", "388927"],
    ["ValorUnitario", None, "Importe", None, None, None, None, None, None, None],
    ["20.590", None, "909.35", None, None, None, None, None, None, None],
]
TABLA_TRASLADOS = [["Impuesto", "Tasao\nCuota", "Importe"], ["IVA", "0.16", "141.32"]]

cargos = ecm._cargos([TABLA_CARGO, TABLA_TRASLADOS])
check(len(cargos) == 1, "una tabla de traslados no se confunde con un cargo: %d" % len(cargos))
c = cargos[0]
check(c["fecha"] == "2026-03-09" and c["hora"] == "19:06:04",
      "fecha y hora se separan aunque vengan pegadas: %r %r" % (c["fecha"], c["hora"]))
check(c["rfc_estacion"] == "FIC120327XYZ", "RFC de estación: %r" % c["rfc_estacion"])
check(c["clave_estacion"] == "9999999", "clave de estación: %r" % c["clave_estacion"])
check(c["cantidad"] == 44.164, "litros: %r" % c["cantidad"])
check(c["nombre_combustible"] == "GasolinaMagnaFleet", "nombre del combustible: %r" % c["nombre_combustible"])
check(c["valor_unitario"] == 20.590 and c["importe"] == 909.35,
      "valor unitario e importe: %r / %r" % (c["valor_unitario"], c["importe"]))

check(ecm._cargos([TABLA_TRASLADOS]) == [], "una página sin ningún bloque de cargo regresa lista vacía")


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
