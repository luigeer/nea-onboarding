# -*- coding: utf-8 -*-
"""
Pruebas de precio_comparado.py.

Se confirmó contra datos reales: en un solo par (cliente de monedero, cliente
de compra directa) que cargan en la MISMA estación, hay 8 días con carga de
ambos lados, y el precio por litro del monedero fue SIEMPRE más bajo — entre
4% y 11%. Estas pruebas usan datos inventados con esa misma forma.

Se corre con:
    python tests/test_precio_comparado.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import precio_comparado as pc

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def carga(rfc_cliente, razon_social, rfc_estacion, fecha, litros, importe):
    return {"rfc_cliente": rfc_cliente, "razon_social": razon_social,
            "rfc_estacion": rfc_estacion, "fecha": fecha,
            "litros": litros, "importe": importe}


# ─────────────────────────────────────────────────────────────────────────────
# comparar(): mismo RFC de estación, mismo día exacto
# ─────────────────────────────────────────────────────────────────────────────
MONEDERO = [
    # Dos cargas de MERQ el mismo día en la misma estación: se promedian.
    carga("MER141216V43", "MERQ", "SFS920210NY3", "2025-10-31", 12.51, 258.03),
    carga("MER141216V43", "MERQ", "SFS920210NY3", "2025-10-31", 12.58, 259.72),
    carga("MER141216V43", "MERQ", "SFS920210NY3", "2025-11-07", 12.66, 259.61),
    # Un día sin contraparte del lado directo: no debe aparecer en el cruce.
    carga("MER141216V43", "MERQ", "SFS920210NY3", "2025-12-25", 10.00, 200.00),
    # Otra estación, sin contraparte directa en absoluto.
    carga("MER141216V43", "MERQ", "EST999999XX9", "2025-10-31", 20.00, 400.00),
]

DIRECTO = [
    carga("JMO211013LY2", "JL MACHINERY", "SFS920210NY3", "2025-10-31",
         62.55, 1348.02),
    carga("JMO211013LY2", "JL MACHINERY", "SFS920210NY3", "2025-11-07",
         40.00, 885.00),
    # Un día sin contraparte del lado monedero: tampoco debe aparecer.
    carga("JMO211013LY2", "JL MACHINERY", "SFS920210NY3", "2025-11-20",
         30.00, 660.00),
]

r = pc.comparar(MONEDERO, DIRECTO)

check(len(r["dias"]) == 2,
      "solo los días con carga de AMBOS lados en la MISMA estación: %d"
      % len(r["dias"]))
d1 = next(d for d in r["dias"] if d["fecha"] == "2025-10-31")
check(d1["rfc_estacion"] == "SFS920210NY3", "la estación del día: %r" % d1)
check(abs(d1["precio_monedero"] - (258.03 + 259.72) / (12.51 + 12.58)) < 1e-3,
      "el precio del monedero promedia las 2 cargas de ese día: %r"
      % d1["precio_monedero"])
check(abs(d1["precio_directo"] - 1348.02 / 62.55) < 1e-3,
      "el precio directo de ese día: %r" % d1["precio_directo"])
check(d1["precio_monedero"] < d1["precio_directo"],
      "en este caso real el monedero sale más barato: %r vs %r"
      % (d1["precio_monedero"], d1["precio_directo"]))
check(abs(d1["diferencia_pct"] -
          (d1["precio_monedero"] - d1["precio_directo"]) / d1["precio_directo"])
      < 1e-4,
      "diferencia_pct es (monedero - directo) / directo, negativo si el "
      "monedero es más barato: %r" % d1["diferencia_pct"])

fechas = {d["fecha"] for d in r["dias"]}
check("2025-12-25" not in fechas and "2025-11-20" not in fechas,
      "los días sin contraparte del otro lado no entran: %r" % fechas)
check(all(d["rfc_estacion"] != "EST999999XX9" for d in r["dias"]),
      "una estación sin ninguna carga directa no aparece")


# ── Agregado por estación ──────────────────────────────────────────────────
check(len(r["estaciones"]) == 1,
      "una sola estación tiene comparación posible: %r" % r["estaciones"])
e = r["estaciones"][0]
check(e["rfc_estacion"] == "SFS920210NY3", "la estación: %r" % e)
check(e["dias_comparados"] == 2, "cuántos días la soportan: %r" % e["dias_comparados"])
check(e["clientes_monedero"] == ["MERQ"], "quién carga vía monedero ahí: %r" % e["clientes_monedero"])
check(e["clientes_directo"] == ["JL MACHINERY"], "quién compra directo: %r" % e["clientes_directo"])
# El promedio de la estación es sobre el TOTAL de litros e importe de los
# días comparados, no el promedio de los promedios diarios.
litros_mon = 12.51 + 12.58 + 12.66
imp_mon = 258.03 + 259.72 + 259.61
litros_dir = 62.55 + 40.00
imp_dir = 1348.02 + 885.00
check(abs(e["precio_monedero"] - imp_mon / litros_mon) < 1e-3,
      "precio del monedero en la estación, sobre el total: %r" % e["precio_monedero"])
check(abs(e["precio_directo"] - imp_dir / litros_dir) < 1e-3,
      "precio directo en la estación, sobre el total: %r" % e["precio_directo"])


# ── Sin traslape, forma vacía y una advertencia de tamaño de muestra ──────
vacio = pc.comparar(
    [carga("A", "A", "EST1", "2025-01-01", 10, 200)],
    [carga("B", "B", "EST2", "2025-01-01", 10, 200)])
check(vacio["dias"] == [] and vacio["estaciones"] == [],
      "sin ninguna estación ni fecha en común, forma vacía: %r" % vacio)

sin_nada = pc.comparar([], [])
check(sin_nada["dias"] == [], "sin ninguna carga, no truena")


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
