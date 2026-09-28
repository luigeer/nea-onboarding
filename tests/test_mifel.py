# -*- coding: utf-8 -*-
"""
Pruebas del lector de estados de cuenta de Banca Mifel.

Igual que en test_bbva.py: aquí NO se prueba la extracción del PDF —eso se
comprueba contra el propio estado de cuenta, que trae sus totales y su saldo
corrido—. Lo que se prueba es `cuadra`, que es lo único que decide si un
estado de cuenta mal leído se guarda o no.

Mifel no da un número de movimientos declarado como BBVA (no hay "Depósitos
(+) N monto"), así que `cuadra` no puede validar cuántos movimientos hubo
contra un dato del banco. Lo que sí publica es el saldo corrido después de
cada movimiento, y eso es una verificación más fuerte: si un solo movimiento
se clasificó al revés (retiro leído como depósito), la cadena de saldos se
rompe en ese renglón exacto, no solo al final.

Todos los datos son inventados.

Se corre con:
    python tests/test_mifel.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mifel

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def mov(tipo, monto, saldo):
    return {"fecha": "01/06/2026", "descripcion": "x", "tipo": tipo,
            "monto": monto, "saldo": saldo}


# ── LO IMPORTANTE · la cadena de saldos ──────────────────────────────────────
print("Cuadre contra el saldo corrido que declara el estado de cuenta")

enc = {"saldo_inicial": 1000.0, "saldo_final": 1300.0,
       "monto_depositos": 500.0, "monto_retiros": 200.0}
buenos = [mov("abono", 500.0, 1500.0), mov("cargo", 200.0, 1300.0)]
ok, _ = mifel.cuadra(enc, buenos)
check(ok, "cuando cada saldo corrido coincide y el final cuadra, cuadra")

# Un movimiento clasificado al revés (depósito leído como retiro) rompe la
# cadena en ese mismo renglón, aunque el saldo final por casualidad coincida.
invertido = [mov("cargo", 500.0, 500.0), mov("abono", 200.0, 700.0)]
ok, d = mifel.cuadra(dict(enc, saldo_final=700.0), invertido)
check(not ok, "un movimiento con la direccion invertida rompe la cadena de saldos")

# El saldo final no coincide con la cadena de movimientos.
ok, d2 = mifel.cuadra(dict(enc, saldo_final=9999.0), buenos)
check(not ok, "si el saldo final declarado no coincide con la cadena, NO cuadra")

# Los montos totales tambien se verifican contra la suma de retiros/depositos.
ok, _ = mifel.cuadra(dict(enc, monto_depositos=999.0), buenos)
check(not ok, "si el total de depositos declarado no coincide con la suma, NO cuadra")

ok, _ = mifel.cuadra({"saldo_inicial": None, "saldo_final": None,
                      "monto_depositos": None, "monto_retiros": None}, buenos)
check(not ok,
      "si el encabezado no se pudo leer, NO cuadra: sin con que comparar no "
      "se declara correcto")

# Sin movimientos no hay nada que reconciliar: no se puede afirmar que cuadra.
ok, _ = mifel.cuadra(enc, [])
check(not ok, "sin movimientos, NO cuadra")

# ── Mifel no declara cuántos movimientos hubo, a diferencia de BBVA ─────────
# ("Depósitos/Abonos (+) N monto"): el conteo se saca de lo que se parseó.
print("Conteo de depositos y retiros, ya que Mifel no lo declara")
movs = [mov("abono", 100.0, 1100.0), mov("abono", 50.0, 1150.0),
        mov("cargo", 30.0, 1120.0)]
deps, ret = mifel._conteos(movs)
check(deps == 2, "cuenta los abonos como depositos")
check(ret == 1, "cuenta los cargos como retiros")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
