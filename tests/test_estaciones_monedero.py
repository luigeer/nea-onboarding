# -*- coding: utf-8 -*-
"""
Pruebas de estaciones_monedero.py.

No se llama a Syntage de verdad: se simula con facturas inventadas. La
lógica que sí importa probar es "¿este subtotal cuenta como monto
simbólico?" y "¿aparece el patrón en 2 de los últimos 3 meses?" — no la
llamada de red en sí.

Se corre con:
    python tests/test_estaciones_monedero.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estaciones_monedero

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── facturas_candidatas(): filtra por monto simbólico ───────────────────────
FACTURAS_MIXTAS = [
    {"uuid": "f1", "subtotal": 1.0, "issuedAt": "2026-06-01 05:59:59"},
    {"uuid": "f2", "subtotal": 45230.50, "issuedAt": "2026-06-15 10:00:00"},
    {"uuid": "f3", "subtotal": 2.09, "issuedAt": "2026-07-01 05:59:59"},
]


class _SyntageDeMentiras(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_MIXTAS


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageDeMentiras
candidatas = estaciones_monedero.facturas_candidatas("cualquier-id", "EFE8908015L3")
estaciones_monedero.syntage = _original_syntage

check(len(candidatas) == 2,
      "solo las facturas de monto simbólico cuentan como candidatas: %d" % len(candidatas))
check({c["folio_fiscal"] for c in candidatas} == {"f1", "f3"},
      "la de $45,230.50 (compra real) queda fuera")
check(candidatas[0]["mes"] == "2026-06",
      "el mes sale de issuedAt, truncado a AAAA-MM: %r" % candidatas[0]["mes"])


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
