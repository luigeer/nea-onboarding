# -*- coding: utf-8 -*-
"""
Pruebas del domicilio del beneficiario controlador en su formato.

Unos expedientes guardan ese domicilio como texto y otros por campos (calle,
número, colonia...). El formato imprime lo que recibe, así que los segundos
salían como "{'calle': 'P DE LA REFORMA', 'num_ext': '1725', ...}" en un
documento que firma el cliente y revisa la autoridad.

Todos los datos son inventados.

Se corre con:
    python tests/test_adaptador_beneficiario.py
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))

from adaptadores import ADAPTADORES
from fixture_paquete import persona_moral

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def test_domicilio_por_campos_sale_en_una_linea():
    e = persona_moral()
    e["beneficiarios_controladores"][0]["domicilio"] = {
        "calle": "P DE LA REFORMA", "num_ext": "1725", "num_int": "B25",
        "colonia": "COOPERATIVA PALO ALTO", "cp": "05110",
        "municipio": "CUAJIMALPA DE MORELOS", "estado": "CIUDAD DE MEXICO"}
    for clave in ("beneficiario_controlador", "grit_beneficiario_controlador"):
        dom = ADAPTADORES[clave](e)["beneficiarios"][0]["domicilio"]
        check(dom == "P DE LA REFORMA 1725, Int. B25, Col. COOPERATIVA PALO ALTO, "
                     "C.P. 05110, CUAJIMALPA DE MORELOS, CIUDAD DE MEXICO",
              "%s imprime el domicilio como dirección (%r)" % (clave, dom))


def test_domicilio_en_texto_queda_igual():
    e = persona_moral()
    e["beneficiarios_controladores"][0]["domicilio"] = "CALLE FALSA 123, CENTRO"
    dom = ADAPTADORES["beneficiario_controlador"](e)["beneficiarios"][0]["domicilio"]
    check(dom == "CALLE FALSA 123, CENTRO", "un domicilio en texto no se toca (%r)" % dom)


def test_no_modifica_el_expediente():
    e = persona_moral()
    ADAPTADORES["beneficiario_controlador"](e)
    check(isinstance(e["beneficiarios_controladores"][0]["domicilio"], dict),
          "el expediente conserva el domicilio por campos")


def main():
    test_domicilio_por_campos_sale_en_una_linea()
    test_domicilio_en_texto_queda_igual()
    test_no_modifica_el_expediente()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
