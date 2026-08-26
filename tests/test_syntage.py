# -*- coding: utf-8 -*-
"""
Prueba de decidir_fiscal(): la unica logica de syntage.py que no depende de
la red y que decide si 'nea.py fiscal' sigue adelante o avisa y para.

Se corre con:
    python tests/test_syntage.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import syntage

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


print("decidir_fiscal()")

r = syntage.decidir_fiscal(entidad=None, completa=False, pendientes=[])
check(r["continuar"] is False, "sin entidad en Syntage, no continua")
check(r["razon"] == "sin_entidad", "y dice por que: falta el alta del cliente")

r = syntage.decidir_fiscal(entidad={"id": "e1"}, completa=False,
                           pendientes=[{"extractor": "tax-returns", "estado": "running"}])
check(r["continuar"] is False, "con extracciones pendientes, no continua")
check(r["razon"] == "pendiente", "y dice que es porque faltan extracciones")
check(r["pendientes"][0]["extractor"] == "tax-returns", "con el detalle de cuales")

r = syntage.decidir_fiscal(entidad={"id": "e1"}, completa=True, pendientes=[])
check(r["continuar"] is True, "con entidad y extraccion completa, si continua")
check("razon" not in r, "y no hay razon para parar, porque no para")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
