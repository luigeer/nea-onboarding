# -*- coding: utf-8 -*-
"""
Corre todas las pruebas y falla si alguna falla.

Existe por un error concreto y repetido: revisar el resultado leyendo la salida
en busca de "Todas las pruebas pasaron". Dos archivos tenían ese texto a media
página porque se les agregaron pruebas después, así que imprimían éxito y salían
con código 0 aunque lo que venía después estuviera rojo. La compuerta del
proyecto estaba abierta y se veía cerrada.

Aquí el veredicto es **el código de salida** de cada archivo, nunca su texto.

Se corre con:
    python tests/todas.py
"""

import glob
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    rojos = []
    for ruta in sorted(glob.glob(os.path.join(AQUI, "test_*.py"))):
        nombre = os.path.basename(ruta)
        r = subprocess.run([sys.executable, ruta], cwd=os.path.dirname(AQUI),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=entorno)
        if r.returncode == 0:
            print("  ok   %s" % nombre)
            continue
        rojos.append(nombre)
        print("ROJO   %s" % nombre)
        for linea in (r.stdout + r.stderr).splitlines():
            if linea.startswith("FALLA") or "Error" in linea:
                print("       %s" % linea)

    print()
    if rojos:
        print("%d archivo(s) en rojo: %s" % (len(rojos), ", ".join(rojos)))
        return 1
    print("Todo verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
