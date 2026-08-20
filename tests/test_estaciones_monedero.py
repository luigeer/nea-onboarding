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
# Horas de media mañana/mediodía UTC a propósito: no cruzan la frontera de
# mes al convertir a hora local (-6h), así que el mes esperado abajo es el
# mismo con o sin la corrección de huso horario del Fix #5 (que se prueba
# aparte, más abajo, con un caso que sí cruza la frontera).
FACTURAS_MIXTAS = [
    {"uuid": "f1", "subtotal": 1.0, "issuedAt": "2026-06-15 12:00:00"},
    {"uuid": "f2", "subtotal": 45230.50, "issuedAt": "2026-06-15 10:00:00"},
    {"uuid": "f3", "subtotal": 2.09, "issuedAt": "2026-07-20 12:00:00"},
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
      "el mes sale de issuedAt, convertido a hora local: %r" % candidatas[0]["mes"])

# ── facturas_candidatas(): el mes se calcula en hora local, no en UTC crudo ─
# Fix #5, confirmado contra datos reales: Efecticard emite su estado de
# cuenta a las 23:59:59 hora de Ciudad de México del último día del mes
# cubierto, que en UTC ya cae en el primer minuto del día siguiente
# (23:59:59 CST = 05:59:59 UTC del día 1). Truncar el string UTC sin
# convertir etiquetaría esta factura como abril en vez de marzo.
FACTURA_EN_LA_FRONTERA = [
    {"uuid": "f-frontera", "subtotal": 1.0, "issuedAt": "2023-04-01 05:59:59"},
]


class _SyntageFrontera(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURA_EN_LA_FRONTERA


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageFrontera
candidatas_frontera = estaciones_monedero.facturas_candidatas("cualquier-id", "EFE8908015L3")
estaciones_monedero.syntage = _original_syntage

check(candidatas_frontera[0]["mes"] == "2023-03",
      "2023-04-01 05:59:59 UTC son las 23:59:59 del 31 de marzo en Ciudad de "
      "México: el mes es marzo, no abril: %r" % candidatas_frontera[0]["mes"])

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
    # Efecticard: patron real, 2 de 3 meses. Horas de mediodía UTC a
    # propósito, para no cruzar la frontera de mes con la corrección de
    # huso horario del Fix #5.
    "EFE8908015L3": [
        {"uuid": "fa", "subtotal": 1.0, "issuedAt": "2026-06-15 12:00:00"},
        {"uuid": "fb", "subtotal": 1.0, "issuedAt": "2026-07-15 12:00:00"},
    ],
    # Petro-7: una sola factura y de monto real -> no es monedero, fue
    # compra directa en la estacion.
    "PET7000000XX": [
        {"uuid": "fc", "subtotal": 3200.0, "issuedAt": "2026-07-15 12:00:00"},
    ],
}


class _SyntagePlanDescarga(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_POR_MONEDERO.get(rfc_emisor, [])


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntagePlanDescarga
plan, sin_revisar = estaciones_monedero.plan_descarga(CLIENTES_DE_PRUEBA, hoy=date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage

check(len(plan) == 2,
      "Efecticard confirmado deja 2 renglones (uno por mes), Petro-7 queda fuera: %d" % len(plan))
check(all(p["rfc_monedero"] == "EFE8908015L3" for p in plan),
      "ningun renglon del plan es de Petro-7 (no paso el patron de recurrencia)")
check({p["mes"] for p in plan} == {"2026-06", "2026-07"},
      "los meses del plan son los que si tuvieron factura candidata")
check(plan[0]["rfc_cliente"] == "CLI001" and plan[0]["nombre_monedero"] == "Efecticard",
      "el renglon trae el contexto completo para ubicar la factura a mano")
check(sin_revisar == [], "sin errores de Syntage, no hay (cliente, monedero) sin revisar")


# ── plan_descarga(): un mes con 2 candidatas simbólicas no se pierde ───────
# Fix #4: confirmar_monedero_real ya no se queda solo con la primera
# candidata de cada mes. Dos tipos de CFDI simbólico del mismo emisor caen
# en julio (el cargo administrativo normal y una comisión aparte por
# fondos insuficientes): ambas deben llegar al plan de descarga, no solo
# una elegida al azar.
CLIENTE_MES_AMBIGUO = [
    {"rfc": "CLI002", "nombre": "CLIENTE DOS", "entidad_id": "e2",
     "hallazgos": [{"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard"}],
     "estado": "ok"},
]

FACTURAS_MES_AMBIGUO = {
    "EFE8908015L3": [
        {"uuid": "ga", "subtotal": 1.0, "issuedAt": "2026-06-15 12:00:00"},
        {"uuid": "gb", "subtotal": 1.0, "issuedAt": "2026-07-15 12:00:00"},
        {"uuid": "gc", "subtotal": 2.09, "issuedAt": "2026-07-16 12:00:00"},
    ],
}


class _SyntageMesAmbiguo(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_MES_AMBIGUO.get(rfc_emisor, [])


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageMesAmbiguo
plan_ambiguo, _sin_revisar_ambiguo = estaciones_monedero.plan_descarga(
    CLIENTE_MES_AMBIGUO, hoy=date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage

check(len(plan_ambiguo) == 3,
      "julio con 2 candidatas produce 2 renglones y junio 1: 3 en total, no se descarta ninguna: %d"
      % len(plan_ambiguo))
folios_julio = {p["folio_fiscal"] for p in plan_ambiguo if p["mes"] == "2026-07"}
check(folios_julio == {"gb", "gc"},
      "ambas facturas simbólicas de julio llegan al plan, no solo la primera: %r" % folios_julio)


# ── plan_descarga(): un ErrorSyntage en un (cliente, monedero) no tumba el resto ─
# Fix #1: facturas_candidatas puede tronar (>= 100 facturas de un emisor, o
# una respuesta truncada a media consulta) para un (cliente, monedero) sin
# que eso descarte el barrido de los demás clientes ya procesados.
CLIENTES_CON_FALLA = [
    {"rfc": "CLI001", "nombre": "CLIENTE UNO", "entidad_id": "e1",
     "hallazgos": [{"rfc_monedero": "ROT0000000XX", "nombre_comercial": "Monedero Roto"}],
     "estado": "ok"},
    {"rfc": "CLI003", "nombre": "CLIENTE TRES", "entidad_id": "e3",
     "hallazgos": [{"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard"}],
     "estado": "ok"},
]

FACTURAS_CON_FALLA = {
    "EFE8908015L3": [
        {"uuid": "ha", "subtotal": 1.0, "issuedAt": "2026-06-15 12:00:00"},
        {"uuid": "hb", "subtotal": 1.0, "issuedAt": "2026-07-15 12:00:00"},
    ],
}


class _SyntageConFalla(object):
    ErrorSyntage = estaciones_monedero.syntage.ErrorSyntage

    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        if rfc_emisor == "ROT0000000XX":
            raise _SyntageConFalla.ErrorSyntage(0, "respuesta incompleta: simulada", "/invoices")
        return FACTURAS_CON_FALLA.get(rfc_emisor, [])


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageConFalla
plan_con_falla, sin_revisar_con_falla = estaciones_monedero.plan_descarga(
    CLIENTES_CON_FALLA, hoy=date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage

check(len(sin_revisar_con_falla) == 1 and sin_revisar_con_falla[0]["rfc_cliente"] == "CLI001",
      "el (cliente, monedero) que truena queda anotado en sin_revisar: %r" % sin_revisar_con_falla)
check(len(plan_con_falla) == 2 and all(p["rfc_cliente"] == "CLI003" for p in plan_con_falla),
      "CLIENTE TRES sigue confirmando su patrón aunque CLIENTE UNO haya tronado: %d renglon(es)"
      % len(plan_con_falla))


# ── plan_descarga(): la ventana se ancla a la última extracción, no a hoy ──
# Descubierto corriendo el barrido real: varios clientes grandes tienen
# credencial vigente pero Syntage no ha vuelto a extraer sus datos en
# semanas o meses. Anclar la ventana a "hoy" los descarta a todos aunque su
# patrón de monedero siga intacto en los datos que sí existen.
CLIENTE_REZAGADO = [
    {"rfc": "CLI004", "nombre": "CLIENTE REZAGADO", "entidad_id": "e4",
     "hallazgos": [{"rfc_monedero": "EFE8908015L3", "nombre_comercial": "Efecticard"}],
     "estado": "ok"},
]

# La última factura es de abril; sin anclar, "hoy" (agosto) deja la ventana
# en junio/julio/agosto y ninguna candidata cae dentro.
FACTURAS_REZAGADAS = {
    "EFE8908015L3": [
        {"uuid": "ia", "subtotal": 1.0, "issuedAt": "2026-02-15 12:00:00"},
        {"uuid": "ib", "subtotal": 1.0, "issuedAt": "2026-03-15 12:00:00"},
        {"uuid": "ic", "subtotal": 1.0, "issuedAt": "2026-04-15 12:00:00"},
    ],
}


class _SyntageRezagado(object):
    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        return FACTURAS_REZAGADAS.get(rfc_emisor, [])

    @staticmethod
    def estado_credenciales(entidad_id):
        return [{"actualizada": "2026-04-20 10:00:00"}]


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageRezagado
plan_rezagado, _ = estaciones_monedero.plan_descarga(CLIENTE_REZAGADO, hoy=date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage

check(len(plan_rezagado) > 0,
      "un cliente con extracción rezagada (última: abril) sí se confirma anclando a esa fecha, "
      "no a hoy (agosto): %d renglon(es)" % len(plan_rezagado))
check({p["mes"] for p in plan_rezagado} == {"2026-02", "2026-03", "2026-04"},
      "los meses confirmados son los de la ventana anclada a abril, no a agosto: %r"
      % {p["mes"] for p in plan_rezagado})


# ── _fecha_ancla(): si no se puede saber, se usa hoy sin tronar ────────────
class _SyntageSinCredenciales(object):
    @staticmethod
    def estado_credenciales(entidad_id):
        return []


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageSinCredenciales
ancla_vacia = estaciones_monedero._fecha_ancla("cualquier-id", date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage
check(ancla_vacia == date(2026, 8, 19), "sin credenciales que consultar, el ancla es hoy")


class _SyntageCredencialesTruena(object):
    @staticmethod
    def estado_credenciales(entidad_id):
        raise RuntimeError("simulado")


_original_syntage = estaciones_monedero.syntage
estaciones_monedero.syntage = _SyntageCredencialesTruena
ancla_con_falla = estaciones_monedero._fecha_ancla("cualquier-id", date(2026, 8, 19))
estaciones_monedero.syntage = _original_syntage
check(ancla_con_falla == date(2026, 8, 19),
      "si consultar credenciales truena, se usa hoy en vez de tumbar el barrido")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
