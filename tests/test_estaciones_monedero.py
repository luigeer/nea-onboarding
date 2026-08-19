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

# ── confirmar_monedero_real(): patrón mensual sobre una ventana fija ───────
HOY = date(2026, 8, 19)

CANDIDATAS_REALES = [
    {"mes": "2026-06", "folio_fiscal": "f1", "subtotal": 1.0, "fecha": "2026-06-01"},
    {"mes": "2026-07", "folio_fiscal": "f2", "subtotal": 1.0, "fecha": "2026-07-01"},
    {"mes": "2025-01", "folio_fiscal": "viejo", "subtotal": 1.0, "fecha": "2025-01-01"},
]
es_real, por_mes = estaciones_monedero.confirmar_monedero_real(CANDIDATAS_REALES, HOY)
check(es_real, "2 de los últimos 3 meses (junio y julio 2026) confirman monedero real")
check(set(por_mes) == {"2026-06", "2026-07"},
      "solo los meses dentro de la ventana quedan en el resultado: %r" % set(por_mes))
check("2025-01" not in por_mes, "una candidata vieja fuera de la ventana no cuenta")

CANDIDATA_UNICA = [
    {"mes": "2026-08", "folio_fiscal": "f3", "subtotal": 1.0, "fecha": "2026-08-01"},
]
es_real_unica, _ = estaciones_monedero.confirmar_monedero_real(CANDIDATA_UNICA, HOY)
check(not es_real_unica, "1 sola coincidencia en la ventana no basta (se requieren 2)")

es_real_vacia, por_mes_vacio = estaciones_monedero.confirmar_monedero_real([], HOY)
check(not es_real_vacia and por_mes_vacio == {}, "sin candidatas no hay monedero real")

# ── plan_descarga(): une facturas_candidatas + confirmar_monedero_real ─────
CLIENTES_DE_PRUEBA = [
    {"rfc": "CLI001", "nombre": "CLIENTE UNO", "entidad_id": "e1",
     "hallazgos": [{"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard"},
                   {"rfc_monedero": "PET7000000XX", "nombre_comercial": "Petro-7"}],
     "estado": "ok"},
]

FACTURAS_POR_MONEDERO = {
    # Efecticard: patron real, 2 de 3 meses.
    "EFE8908015L3": [
        {"uuid": "fa", "subtotal": 1.0, "issuedAt": "2026-06-01 00:00:00"},
        {"uuid": "fb", "subtotal": 1.0, "issuedAt": "2026-07-01 00:00:00"},
    ],
    # Petro-7: una sola factura y de monto real -> no es monedero, fue
    # compra directa en la estacion.
    "PET7000000XX": [
        {"uuid": "fc", "subtotal": 3200.0, "issuedAt": "2026-07-15 00:00:00"},
    ],
}


class _SyntagePlanDescarga(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_POR_MONEDERO.get(rfc_emisor, [])


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntagePlanDescarga
plan = estaciones_monedero.plan_descarga(CLIENTES_DE_PRUEBA, hoy=date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage

check(len(plan) == 2,
      "Efecticard confirmado deja 2 renglones (uno por mes), Petro-7 queda fuera: %d" % len(plan))
check(all(p["rfc_monedero"] == "EFE8908015L3" for p in plan),
      "ningun renglon del plan es de Petro-7 (no paso el patron de recurrencia)")
check({p["mes"] for p in plan} == {"2026-06", "2026-07"},
      "los meses del plan son los que si tuvieron factura candidata")
check(plan[0]["rfc_cliente"] == "CLI001" and plan[0]["nombre_monedero"] == "Efecticard",
      "el renglon trae el contexto completo para ubicar la factura a mano")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
