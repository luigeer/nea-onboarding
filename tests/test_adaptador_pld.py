# -*- coding: utf-8 -*-
"""
Pruebas del domicilio en los formatos PLD (Anexo 4 y Anexo 3).

El renglón del formato dice "No. Exterior/Interior", pero el adaptador solo
mandaba el exterior: un cliente en "Prol. Reforma 1725 int. B 25 y 26" salía en
el PLD como "1725", que es otro domicilio para quien lo verifica.

Todos los datos son inventados.

Se corre con:
    python tests/test_adaptador_pld.py
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


def test_el_pld_lleva_el_numero_interior():
    e = persona_moral()
    e["cliente"]["validado"]["domicilio"].update({"num_ext": "1725", "num_int": "B 25 Y 26"})
    for clave in ("pld_pm", "grit_pld_pm"):
        n = ADAPTADORES[clave](e)["num_ext"]
        check(n == "1725 INT. B 25 Y 26", "%s lleva exterior e interior (%r)" % (clave, n))


def test_sin_interior_queda_solo_el_exterior():
    e = persona_moral()
    for clave in ("pld_pm", "grit_pld_pm"):
        n = ADAPTADORES[clave](e)["num_ext"]
        check(n == "123", "%s sin interior deja el exterior tal cual (%r)" % (clave, n))


def main():
    test_el_pld_lleva_el_numero_interior()
    test_sin_interior_queda_solo_el_exterior()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
