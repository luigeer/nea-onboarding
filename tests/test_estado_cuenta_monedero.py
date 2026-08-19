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
check(c["identificador"] == "XXXXXXXXXXXX\n0001",
      "identificador de tarjeta: %r" % c["identificador"])
check(c["tipo_combustible"] == "1", "tipo de combustible: %r" % c["tipo_combustible"])
check(c["folio_operacion"] == "388927", "folio de operación: %r" % c["folio_operacion"])

check(ecm._cargos([TABLA_TRASLADOS]) == [], "una página sin ningún bloque de cargo regresa lista vacía")


# ── cuadra(): la suma de importes contra el subtotal declarado ────────────
CARGOS_DE_PRUEBA = [
    {"rfc_estacion": "FIC120327XYZ", "clave_estacion": "9999999", "cantidad": 44.164, "importe": 909.35},
    {"rfc_estacion": "FIC120327XYZ", "clave_estacion": "9999999", "cantidad": 20.0, "importe": 410.00},
    {"rfc_estacion": "OTR050101ABC", "clave_estacion": "1234567", "cantidad": 30.0, "importe": 615.00},
]

check(ecm.cuadra(CARGOS_DE_PRUEBA, {"subtotal": 1934.35}),
      "la suma de importes (1934.35) cuadra contra el subtotal declarado")
check(not ecm.cuadra(CARGOS_DE_PRUEBA, {"subtotal": 5000.0}),
      "una diferencia grande no cuadra: el PDF se marca sospechoso")
check(not ecm.cuadra(CARGOS_DE_PRUEBA, None),
      "sin resumen de cuenta (no se encontró la tabla), nunca cuadra")


# ── agregar_por_estacion(): por (RFC, clave) de estación ───────────────────
agregado = ecm.agregar_por_estacion(CARGOS_DE_PRUEBA)
check(len(agregado) == 2, "dos estaciones distintas: %d" % len(agregado))
clave_repetida = ("FIC120327XYZ", "9999999")
check(agregado[clave_repetida]["cargas"] == 2,
      "dos cargos en la misma estación se agregan, no se cuentan como estaciones distintas")
check(abs(agregado[clave_repetida]["importe"] - 1319.35) < 0.01,
      "importe total de esa estación: %r" % agregado[clave_repetida]["importe"])
check(abs(agregado[clave_repetida]["litros"] - 64.164) < 0.01,
      "litros totales de esa estación: %r" % agregado[clave_repetida]["litros"])


# ── agregar_por_estacion(): el par (RFC, clave), no un solo campo ──────────
# Prueba que dos monederos distintos pueden reusarcodigos de estacion internos:
# agregar_por_estacion debe usar la CLAVE como el par (rfc, clave), no solo
# el numero de clave. Si solo usara la clave, esta cargo se juntaria con
# FIC120327XYZ/9999999 (pero tiene RFC distinto); si solo usara RFC, se
# juntaria con OTR050101ABC/1234567 (pero tiene clave distinta).
CARGOS_CLAVE_COMPARTIDA = CARGOS_DE_PRUEBA + [
    {"rfc_estacion": "OTR050101ABC", "clave_estacion": "9999999", "cantidad": 10.0, "importe": 200.00},
]
agregado_compartido = ecm.agregar_por_estacion(CARGOS_CLAVE_COMPARTIDA)
check(len(agregado_compartido) == 3,
      "misma clave_estacion bajo distinto rfc_estacion NO se junta: %d estaciones" % len(agregado_compartido))
check(("OTR050101ABC", "9999999") in agregado_compartido,
      "el nuevo par (rfc, clave) tiene su propia entrada, separada de FIC120327XYZ/9999999")
check(abs(agregado_compartido[("OTR050101ABC", "9999999")]["importe"] - 200.00) < 0.01,
      "importe del nuevo par es independiente: %r" % agregado_compartido[("OTR050101ABC", "9999999")]["importe"])


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
