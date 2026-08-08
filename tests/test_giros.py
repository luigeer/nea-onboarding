# -*- coding: utf-8 -*-
"""
Pruebas de la tabla de Giro.

Lo que se prueba no es que la clasificación sea "correcta" —eso es un juicio de
negocio— sino que el orden de las reglas haga lo que dice: que la naturaleza
del servicio le gane al sector al que le vende, y que la actividad que el
propio contribuyente declaró como principal mande sobre las demás.

Nombres de actividad tomados del catálogo oficial del SAT.

Se corre con:
    python tests/test_giros.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import giros

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


print("Los seis códigos")
check(sorted(giros.CODIGOS) == ["Codigo %d" % i for i in range(1, 7)],
      "son exactamente seis, del 1 al 6")
pesos = [giros.peso("Codigo %d" % i) for i in range(1, 7)]
check(pesos == sorted(pesos, reverse=True),
      "y sus pesos bajan monótonamente: a ciclo más largo, peor calificación")

print("Clasificación por ciclo de cobro")
casos = [
    ("Comercio al por menor de mascotas, medicamentos y accesorios", "Codigo 1"),
    ("Autotransporte foráneo de carga general", "Codigo 2"),
    ("Comercio al por mayor de medicamentos veterinarios", "Codigo 3"),
    ("Fabricación de productos de plástico", "Codigo 4"),
    ("Construcción de obras de urbanización", "Codigo 5"),
    ("Compraventa y fraccionamiento de bienes inmobiliarios", "Codigo 6"),
]
for actividad, esperado in casos:
    obtenido, _ = giros.sugerir(actividad)
    check(obtenido == esperado,
          "%s -> %s" % (actividad[:44], esperado))

print("LO IMPORTANTE · el servicio le gana al sector al que le vende")
cod, _ = giros.sugerir(
    "Servicios veterinarios para la ganadería prestados por el sector privado")
check(cod == "Codigo 3",
      "un veterinario que atiende ganaderías cobra como servicio, no como ganadería")
cod, _ = giros.sugerir("Transporte de materiales para la construcción")
check(cod == "Codigo 2",
      "y un transportista que mueve material de obra cobra al entregar, no a estimaciones")

print("Manda la actividad principal declarada")
actividades = [
    {"name": "Comercio al por mayor de medicamentos veterinarios", "percentage": 50},
    {"name": "Otros intermediarios del comercio al por menor", "percentage": 30},
    {"name": "Comercio al por menor de mascotas", "percentage": 10},
]
cod, desglose = giros.sugerir_de_actividades(actividades)
check(cod == "Codigo 3", "gana la de mayor porcentaje, no la primera de la lista")
check(len(desglose) == 3, "y el desglose conserva todas para que el operador las vea")
check(all(d["coincidencia"] for d in desglose),
      "cada renglón dice qué palabra disparó su código")

cod, _ = giros.sugerir_de_actividades([
    {"name": "Actividad que no se parece a nada", "percentage": 100}])
check(cod is None,
      "una actividad que no coincide con nada no se inventa un código")

cod, _ = giros.sugerir_de_actividades([])
check(cod is None, "y sin actividades tampoco")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
