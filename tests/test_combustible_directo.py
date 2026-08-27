# -*- coding: utf-8 -*-
"""
Pruebas de combustible_directo.py.

Las facturas son inventadas, con la forma exacta que entrega la API de
Syntage — se copió de facturas reales de dos clientes que le compran gasolina
directo a una gasolinera, sin monedero de por medio.

Se corre con:
    python tests/test_combustible_directo.py
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import combustible_directo as cd

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def item(clave, desc, litros, precio, permiso, unidad="LTR"):
    return {"productIdentification": clave, "description": desc,
            "quantity": litros, "unitAmount": precio, "unitCode": unidad,
            "totalAmount": round(litros * precio, 2),
            "identificationNumber": "%s - 322059" % permiso}


# ─────────────────────────────────────────────────────────────────────────────
# es_combustible(): la clave del SAT, no el texto libre
# ─────────────────────────────────────────────────────────────────────────────
# Las tres claves que aparecen en datos reales: Magna, Pemex Diesel, Premium.
for clave, desc in (("15101514", "MAGNA"), ("15101505", "PEMEX DIESEL"),
                    ("15101515", "PREMIUM")):
    check(cd.es_combustible(item(clave, desc, 50.0, 20.0, "PL/1443/EXP/ES/2015")),
          "%s (%s) es combustible" % (clave, desc))

# La unidad la escriben mal algunos emisores: en datos reales, 49 de 410
# conceptos traen unitCode "10" en vez de "LTR", con la MISMA clave del SAT y
# la misma descripción. Exigir "LTR" perdería esas facturas completas.
check(cd.es_combustible(item("15101514", "MAGNA", 50.0, 20.0,
                             "PL/1443/EXP/ES/2015", unidad="10")),
      "un unitCode equivocado no descalifica: manda la clave del SAT")

# Lo que no es combustible: la clave del SAT lo dice, aunque el texto engañe.
check(not cd.es_combustible(item("15121500", "ACEITE MOTOR", 4.0, 200.0, "")),
      "un lubricante (15121500) no es combustible aunque se venda por litro")
check(not cd.es_combustible({"productIdentification": "15101514",
                             "description": "MAGNA", "quantity": 0,
                             "totalAmount": 0}),
      "un concepto sin litros no cuenta: no hay carga que medir")
check(not cd.es_combustible({}), "un item vacío no truena")


# ─────────────────────────────────────────────────────────────────────────────
# desglosar(): por estación (permiso CRE) y por mes
# ─────────────────────────────────────────────────────────────────────────────
FACTURAS = [
    # Dos cargas en la misma estación, misma factura.
    {"uuid": "f1", "type": "I", "xml": True, "issuedAt": "2026-03-10 12:00:00",
     "subtotal": 2000.0, "issuer": {"rfc": "GAS010101AA1", "name": "GASOLINERA UNO"},
     "receiver": {"rfc": "CLI020202BB2", "name": "CLIENTE UNO"},
     "items": [item("15101514", "MAGNA", 50.0, 20.0, "PL/1443/EXP/ES/2015"),
               item("15101515", "PREMIUM", 40.0, 25.0, "PL/1443/EXP/ES/2015")]},
    # Otra estación del MISMO emisor: el permiso CRE las distingue.
    {"uuid": "f2", "type": "I", "xml": True, "issuedAt": "2026-04-05 12:00:00",
     "subtotal": 600.0, "issuer": {"rfc": "GAS010101AA1", "name": "GASOLINERA UNO"},
     "receiver": {"rfc": "CLI020202BB2", "name": "CLIENTE UNO"},
     "items": [item("15101505", "PEMEX DIESEL", 30.0, 20.0, "PL/6296/EXP/ES/2015")]},
    # Una factura sin XML en Syntage: se detectó en los metadatos del SAT pero
    # el documento nunca se extrajo. Sus montos vienen vacíos y contarla
    # sumaría ceros que se ven como datos.
    {"uuid": "f3", "type": "I", "xml": False, "issuedAt": "2026-04-20 12:00:00",
     "subtotal": None, "issuer": {"rfc": "GAS010101AA1", "name": "GASOLINERA UNO"},
     "receiver": {"rfc": "CLI020202BB2", "name": "CLIENTE UNO"}, "items": []},
    # Un complemento de pago no es una compra.
    {"uuid": "f4", "type": "P", "xml": True, "issuedAt": "2026-04-25 12:00:00",
     "subtotal": 2600.0, "issuer": {"rfc": "GAS010101AA1", "name": "GASOLINERA UNO"},
     "receiver": {"rfc": "CLI020202BB2", "name": "CLIENTE UNO"},
     "items": [{"description": "Pago", "totalAmount": 2600.0}]},
    # Una factura del mismo emisor que no es combustible: no entra.
    {"uuid": "f5", "type": "I", "xml": True, "issuedAt": "2026-04-28 12:00:00",
     "subtotal": 800.0, "issuer": {"rfc": "GAS010101AA1", "name": "GASOLINERA UNO"},
     "receiver": {"rfc": "CLI020202BB2", "name": "CLIENTE UNO"},
     "items": [item("15121500", "ACEITE MOTOR", 4.0, 200.0, "")]},
]

d = cd.desglosar(FACTURAS)

check(d["facturas"] == 2,
      "solo las 2 facturas de combustible con XML: ni el pago, ni el aceite, "
      "ni la que Syntage no tiene — %r" % d["facturas"])
check(d["importe"] == 2600.0,
      "importe: $1,000 magna + $1,000 premium + $600 diesel = %r" % d["importe"])
check(d["litros"] == 120.0, "litros: 50 + 40 + 30 = %r" % d["litros"])
check(sorted(d["meses"]) == ["2026-03", "2026-04"],
      "los meses: %r" % sorted(d["meses"]))
check(d["meses"]["2026-03"]["importe"] == 2000.0,
      "marzo: %r" % d["meses"]["2026-03"])

# El precio promedio por litro es lo que permite comparar contra un monedero
# en la misma estación: $2,600 / 120 litros = $21.67.
check(abs(d["precio_litro"] - 2600.0 / 120.0) < 1e-9,
      "precio promedio por litro: %r" % d["precio_litro"])

# ── cargas: el detalle día a día, para cruzar contra el monedero ──────────
check(len(d["cargas"]) == 3,
      "una carga por concepto de combustible, sin agregar: %r" % len(d["cargas"]))
por_fecha = {(c["fecha"], c["rfc_estacion"]): c for c in d["cargas"]}
check(por_fecha[("2026-03-10", "GAS010101AA1")]["litros"] in (50.0, 40.0),
      "cada carga trae su propia fecha y estación: %r" % d["cargas"])
check(sum(c["importe"] for c in d["cargas"]) == d["importe"],
      "la suma de las cargas cuadra con el importe total: %r"
      % [sum(c["importe"] for c in d["cargas"]), d["importe"]])


# ── Por estación: el permiso CRE, no el RFC del emisor ────────────────────
# Un solo emisor factura por 35 permisos distintos en datos reales: agrupar
# por RFC juntaría 35 gasolineras en un renglón, que es justo el error que ya
# se cometió con las estaciones de monedero.
est = {(e["rfc_emisor"], e["permiso"]): e for e in d["estaciones"]}
check(len(est) == 2,
      "dos estaciones del mismo emisor, separadas por permiso CRE: %r" % list(est))
e1 = est[("GAS010101AA1", "PL/1443/EXP/ES/2015")]
check(e1["importe"] == 2000.0 and e1["litros"] == 90.0,
      "la estación del permiso 1443: %r" % e1)
check(e1["cargas"] == 2, "dos cargas en esa estación: %r" % e1["cargas"])
check(abs(e1["precio_litro"] - 2000.0 / 90.0) < 1e-9,
      "su precio por litro: %r" % e1["precio_litro"])
check(sorted(e1["combustibles"]) == ["MAGNA", "PREMIUM"],
      "qué combustibles se cargaron ahí: %r" % e1["combustibles"])
check(d["estaciones"][0]["importe"] >= d["estaciones"][-1]["importe"],
      "las estaciones vienen ordenadas por importe: %r"
      % [e["importe"] for e in d["estaciones"]])


# ── Un permiso vacío no se confunde con una estación ──────────────────────
sin_permiso = cd.desglosar([
    {"uuid": "g1", "type": "I", "xml": True, "issuedAt": "2026-03-10 12:00:00",
     "subtotal": 400.0, "issuer": {"rfc": "GAS010101AA1", "name": "GASOLINERA UNO"},
     "receiver": {"rfc": "CLI020202BB2", "name": "CLIENTE UNO"},
     "items": [item("15101514", "MAGNA", 20.0, 20.0, "")]}])
check(sin_permiso["estaciones"][0]["permiso"] == "",
      "una carga sin permiso CRE se reporta con permiso vacío, no se descarta: "
      "%r" % sin_permiso["estaciones"][0])
check(sin_permiso["importe"] == 400.0, "y su importe sí cuenta")


# ── Nada de combustible: forma vacía, no basura ───────────────────────────
vacio = cd.desglosar([])
check(vacio["facturas"] == 0 and vacio["estaciones"] == []
      and vacio["precio_litro"] is None,
      "sin facturas, forma vacía y precio None (no cero): %r" % vacio)


# ─────────────────────────────────────────────────────────────────────────────
# recolectar(): caché con versión, igual que comisiones_monedero
# ─────────────────────────────────────────────────────────────────────────────
CARPETA = tempfile.mkdtemp(prefix="_prueba_combustible_")
llamadas = []


class _SyntageFalso(object):
    @staticmethod
    def id_entidad(rfc):
        return "eid-" + rfc

    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        llamadas.append((entidad_id, rfc_emisor))
        return FACTURAS


_original = cd.syntage
cd.syntage = _SyntageFalso

PARES = [("CLI020202BB2", "GAS010101AA1")]
r1 = cd.recolectar(PARES, carpeta=CARPETA)
check(len(llamadas) == 1, "una llamada por par: %r" % llamadas)
check(r1[("CLI020202BB2", "GAS010101AA1")]["importe"] == 2600.0,
      "recolectar() devuelve el desglose: %r"
      % r1[("CLI020202BB2", "GAS010101AA1")]["importe"])

r2 = cd.recolectar(PARES, carpeta=CARPETA)
check(len(llamadas) == 1, "la segunda corrida sale del caché: %r" % llamadas)

ruta_cache = os.path.join(CARPETA, "CLI020202BB2_GAS010101AA1.json")
with open(ruta_cache, encoding="utf-8") as fh:
    guardado = json.load(fh)
guardado["version"] = cd.VERSION_CACHE - 1
guardado["importe"] = 999999.0
with open(ruta_cache, "w", encoding="utf-8") as fh:
    json.dump(guardado, fh)
r3 = cd.recolectar(PARES, carpeta=CARPETA)
check(len(llamadas) == 2,
      "un caché de versión anterior se vuelve a pedir: %r" % llamadas)
check(r3[("CLI020202BB2", "GAS010101AA1")]["importe"] == 2600.0,
      "y no se usan sus números viejos: %r"
      % r3[("CLI020202BB2", "GAS010101AA1")]["importe"])


class _SyntageQueFalla(object):
    @staticmethod
    def id_entidad(rfc):
        raise LookupError("no está dado de alta")

    @staticmethod
    def facturas(entidad_id, rfc_emisor):           # pragma: no cover
        raise AssertionError("no debería llegar aquí")


cd.syntage = _SyntageQueFalla
r4 = cd.recolectar([("NADIE0000XX1", "GAS010101AA1")],
                   carpeta=tempfile.mkdtemp(prefix="_prueba_combustible_2_"))
entrada = r4[("NADIE0000XX1", "GAS010101AA1")]
check(entrada["error"] is not None,
      "un cliente que Syntage no conoce queda con el motivo anotado: %r" % entrada)
check(entrada["importe"] == 0.0, "y con importe en cero, no con basura")

cd.syntage = _original
shutil.rmtree(CARPETA, ignore_errors=True)


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
