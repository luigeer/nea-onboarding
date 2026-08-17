# -*- coding: utf-8 -*-
"""
Pruebas del lector de estados de cuenta de BBVA.

Aquí NO se prueba la extracción del PDF: eso se comprueba contra el propio
estado de cuenta, que trae los totales calculados por el banco, y esa
comprobación (`cuadra`) vale más que cualquier prueba con un PDF de mentiras.
Lo que se prueba es la clasificación, que es donde está el juicio de negocio:

- que un depósito en efectivo no se confunda con uno identificable, porque es
  la distinción central para PLD;
- que un SPEI devuelto no cuente como ingreso, porque es dinero propio que
  rebotó y el banco lo suma a los depósitos del periodo;
- que `cuadra` diga que NO cuando no cuadra, que es lo único que impide guardar
  un estado de cuenta mal leído.

Todos los datos son inventados.

Se corre con:
    python tests/test_bbva.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bbva

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def ab(codigo, monto):
    return {"codigo": codigo, "monto": monto, "tipo": "abono",
            "descripcion": "x", "fecha": "01/ABR"}


def ca(codigo, monto):
    return dict(ab(codigo, monto), tipo="cargo")


# ── LO IMPORTANTE · el efectivo se separa ────────────────────────────────────
print("Clasificacion del origen del deposito")
movs = [ab("C02", 20000.0), ab("AA7", 4178.0),      # efectivo
        ab("T20", 15000.0), ab("T09", 5000.0),      # SPEI / TEF recibido
        ab("W02", 57330.28), ab("AP6", 202511.52),  # deposito de tercero
        ab("N03", 50000.0),                          # traspaso entre cuentas propias
        ab("T22", 108037.5)]                         # SPEI devuelto
g = bbva.clasificar(movs)
check(g["efectivo"]["monto"] == 24178.0 and g["efectivo"]["numero"] == 2,
      "el efectivo se agrupa aparte: es el deposito sin ordenante identificable")
check(g["spei"]["monto"] == 20000.0, "SPEI y TEF recibidos cuentan como identificables")
check(g["tercero"]["monto"] == 259841.8,
      "los depositos de tercero incluyen los que entran por API")

# Un traspaso entre cuentas del mismo titular no es ingreso del negocio.
check(g["cuentas_propias"]["monto"] == 50000.0,
      "el traspaso entre cuentas propias no se mezcla con el ingreso de terceros")

# LO IMPORTANTE: el SPEI devuelto no es un ingreso.
check(g["devoluciones"]["monto"] == 108037.5,
      "un SPEI devuelto va a su propia categoria")
check("devoluciones" in g and g["devoluciones"]["monto"] not in
      (g["spei"]["monto"], g["tercero"]["monto"]),
      "y NO se suma al ingreso: es dinero propio que reboto, no dinero que entro")

check(g["otro"]["numero"] == 0, "sin codigos raros no queda nada sin clasificar")

# Un codigo que no conocemos cae en 'otro' y se ve, en vez de repartirse.
g2 = bbva.clasificar([ab("ZZ9", 1000.0)])
check(g2["otro"]["monto"] == 1000.0,
      "un codigo desconocido queda visible en 'otro', no adivinado")

# Los cargos no entran a la clasificacion de depositos.
g3 = bbva.clasificar([ca("T17", 111853.65), ab("C02", 100.0)])
check(g3["efectivo"]["monto"] == 100.0 and sum(
    v["monto"] for v in g3.values()) == 100.0,
    "un cargo no se cuenta como deposito")

# ── LO IMPORTANTE · la compuerta contra el resumen del banco ─────────────────
print("Cuadre contra los totales que declara el banco")
enc = {"monto_depositos": 300.0, "numero_depositos": 2,
       "monto_retiros": 50.0, "numero_retiros": 1}
buenos = [ab("C02", 100.0), ab("T20", 200.0), ca("T17", 50.0)]
ok, _ = bbva.cuadra(enc, buenos)
check(ok, "cuando coincide monto y numero, cuadra")

ok, d = bbva.cuadra(enc, [ab("C02", 100.0), ca("T17", 50.0)])
check(not ok, "si falta un deposito, NO cuadra")
check(d["depositos_numero"] == (1, 2), "y el diagnostico dice en que difiere")

ok, _ = bbva.cuadra(enc, [ab("C02", 100.0), ab("T20", 199.0), ca("T17", 50.0)])
check(not ok, "un peso de diferencia tampoco pasa")

ok, _ = bbva.cuadra({"monto_depositos": None, "numero_depositos": None,
                     "monto_retiros": None, "numero_retiros": None}, buenos)
check(not ok,
      "si el resumen del banco no se pudo leer, NO cuadra: sin con que comparar "
      "no se declara correcto")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
