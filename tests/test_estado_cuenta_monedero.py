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


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
