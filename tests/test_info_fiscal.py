# -*- coding: utf-8 -*-
"""
Pruebas de la proyección de los insights de Syntage a `info_fiscal`.

Lo que se está probando es una sola distinción, y es la que mueve el score: un
ejercicio sin declarar viene entero en null; uno declarado trae ceros donde el
SAT calculó y nulls donde el contribuyente no llenó, y ahí el null es un cero.

Todos los datos son inventados. La forma del árbol sí es la real.

Se corre con:
    python tests/test_info_fiscal.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import info_fiscal

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def nodo(categoria, valores, hijos=None):
    """Un nodo del insight: {"2023": {"Total": x}, "category": ..., ...}"""
    n = {"category": categoria}
    n.update({a: {"Total": v, "Comment": None} for a, v in valores.items()})
    if hijos:
        n["children"] = hijos
    return n


# 2023 sin declarar (todo null), 2024 y 2025 declarados.
NADA = {"2023": None, "2024": None, "2025": None}
BALANCE = {"data": [
    nodo("Activo", {"2023": None, "2024": 500000.0, "2025": 640000.0}, [
        nodo("Activo a corto plazo", {"2023": None, "2024": 500000.0, "2025": 640000.0}, [
            nodo("Inventario de materia prima", {"2023": None, "2024": 20000.0, "2025": 25000.0}),
            nodo("Inventario de producto terminado", {"2023": None, "2024": 5000.0, "2025": 7000.0}),
        ]),
    ]),
    nodo("Pasivo", {"2023": None, "2024": 200000.0, "2025": 210000.0}, [
        nodo("Pasivo a corto plazo", {"2023": None, "2024": 200000.0, "2025": 210000.0}),
    ]),
    nodo("Capital", {"2023": None, "2024": 300000.0, "2025": 430000.0}, [
        nodo("Capital contable", {"2023": None, "2024": 300000.0, "2025": 430000.0}),
    ]),
]}

# 2024 con ingresos; 2025 declarado con las utilidades en cero y el renglón de
# ingresos en blanco, que es el caso que importa.
RESULTADOS = {"data": [
    nodo("Ingresos Netos", {"2023": None, "2024": 4000000.0, "2025": None}),
    nodo("Utilidad Bruta", {"2023": None, "2024": 900000.0, "2025": 0.0}),
    nodo("Utilidad de operación", {"2023": None, "2024": 600000.0, "2025": 0.0}, [
        nodo("Utilidad de operación", {"2023": None, "2024": 111.0, "2025": 222.0}),
    ]),
]}


print("Qué ejercicios están declarados")
anios = info_fiscal.ejercicios_declarados(BALANCE, RESULTADOS)
check(anios == [2024, 2025],
      "un ejercicio entero en null no está declarado y no produce fila")

filas = {f["ejercicio"]: f for f in info_fiscal.desde_insights(BALANCE, RESULTADOS)}
check(2023 not in filas, "y por eso 2023 no aparece")

print("Un ejercicio con cifras")
f = filas[2024]
check(f["ingresos_totales"] == 4000000.0, "los ingresos salen de Ingresos Netos")
check(f["utilidad_operacion"] == 600000.0,
      "y la utilidad del nodo de arriba, no del hijo que repite el nombre")
check(f["activo_corto_plazo"] == 500000.0 and f["pasivo_corto_plazo"] == 200000.0,
      "el balance sale del subgrupo de corto plazo, no del grupo")
check(f["capital_contable"] == 300000.0, "y el capital contable de su renglón")
check(f["inventarios"] == 25000.0, "los inventarios se suman de todas sus ramas")

print("LO IMPORTANTE · un ejercicio declarado con el renglón en blanco")
f = filas[2025]
check(f["ingresos_totales"] == 0.0,
      "ingresos en blanco dentro de un ejercicio declarado se leen como cero")
check(f["declarado"] is True, "y la fila queda marcada como declarada")
check(f["utilidad_operacion"] == 0.0, "la utilidad cero se conserva como cero")

print("Pérdidas")
PERDIDA = {"data": [
    nodo("Ingresos Netos", {"2025": 1000000.0}),
    nodo("Pérdida de operación", {"2025": 250000.0}),
]}
f = info_fiscal.desde_insights({"data": []}, PERDIDA)[0]
check(f["utilidad_operacion"] == -250000.0,
      "una pérdida llega en positivo desde el SAT y se le invierte el signo")

print("Sin nada")
check(info_fiscal.desde_insights({"data": []}, {"data": []}) == [],
      "sin ningún ejercicio declarado no se escribe ninguna fila")
check(info_fiscal.desde_insights(None, None) == [],
      "y un payload ausente no revienta")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
