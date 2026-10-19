# -*- coding: utf-8 -*-
"""
Pruebas del lector de "Actividades Económicas" de la CSF cuando la tabla no sale
como tabla y hay que leerla del texto.

Caso que lo originó: con una CSF real la tabla de pdfplumber solo trajo los
encabezados (los renglones quedaron en la página siguiente) y el expediente se
abrió con `actividades: []`. La actividad se tuvo que capturar a mano.

El texto de abajo es inventado, pero reproduce las tres cosas que rompían la
lectura:

  - renglones sin espacios ("Comerciomayoristadeartículosvarios")
  - una descripción partida en dos renglones, con el porcentaje pegado al final
    del primero ("...de equipo y otros30 01/10/2022" / "serviciosconexos")
  - la tabla cruzando el salto de página, con el pie "Página 1 de 3" en medio

Se corre con:
    python tests/test_csf_actividades.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraer_csf import _actividades_texto, _actividad_principal

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


TEXTO = """Nombre de la Entidad Federativa: JALISCO Entre Calle: CALLE UNO
Y Calle: CALLE DOS
Actividades Económicas:
Orden Actividad Económica Porcentaje Fecha Inicio Fecha Fin
Página 1 de 3
1 Comerciomayoristadeartículosvarios 40 05/07/2006
2 Reparación, mantenimiento de equipo y otros30 01/10/2022
serviciosconexos
3 Servicios de mensajería 30 01/11/2022
Regímenes:
Régimen Fecha Inicio Fecha Fin
Régimen General de Ley Personas Morales 08/04/2006
"""

print("Actividades leídas del texto")
acts = _actividades_texto(TEXTO)
check(len(acts) == 3, "reconoce las tres actividades (salieron %d)" % len(acts))
if len(acts) == 3:
    check([a["porcentaje"] for a in acts] == [40.0, 30.0, 30.0],
          "con su porcentaje, aunque venga pegado a la descripción")
    check([a["fecha_inicio"] for a in acts] == ["2006-07-05", "2022-10-01", "2022-11-01"],
          "y con su fecha de inicio")
    check(acts[0]["actividad"] == "Comerciomayoristadeartículosvarios",
          "el renglón sin espacios se lee completo")
    check(acts[1]["actividad"] == "Reparación, mantenimiento de equipo y otros serviciosconexos",
          "la descripción partida en dos renglones se une en una sola")
    check(acts[2]["actividad"] == "Servicios de mensajería",
          "el renglón normal sale tal cual")
    check([a["orden"] for a in acts] == [1, 2, 3], "y conserva el orden del SAT")

print("Actividad principal")
p = _actividad_principal(acts)
check(p is not None and p["actividad"] == "Comerciomayoristadeartículosvarios",
      "es la de mayor porcentaje")
p = _actividad_principal([
    {"orden": 1, "actividad": "Menor", "porcentaje": 10.0, "fecha_inicio": None},
    {"orden": 2, "actividad": "Mayor", "porcentaje": 90.0, "fecha_inicio": None}])
check(p["actividad"] == "Mayor", "aunque no sea la primera de la lista")
check(_actividad_principal([]) is None, "y sin actividades no se inventa una")

print("Lo que no es la tabla no se lee como actividad")
check(_actividades_texto("Regímenes:\nRégimen General 08/04/2006\n") == [],
      "un texto sin la sección de actividades regresa lista vacía")
otra = _actividades_texto(TEXTO.replace("Página 1 de 3\n", "")
                          .replace("serviciosconexos\n",
                                   "serviciosconexos\nCadena Original Sello: ||2026/09/18|ABC|\n"))
check(len(otra) == 3 and otra[1]["actividad"].endswith("serviciosconexos"),
      "el pie de página con el sello no se pega a la descripción")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
