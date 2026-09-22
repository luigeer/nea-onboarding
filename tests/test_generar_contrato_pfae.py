# -*- coding: utf-8 -*-
"""
Pruebas de generar_contrato_pfae.py: el nombre del cliente en el bloque de
firma debe quedar DEBAJO de la línea de firma, en el mismo renglón que la
etiqueta "Nombre:" (igual que "Marcos Siqueiros Ballesteros" aparece junto a
su renglón en la columna de Nea) — no arriba de la línea, y sin invadir la
columna derecha (firma de Nea).

Se corre con:
    python tests/test_generar_contrato_pfae.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generadores"))

import pdfplumber

from generar_contrato_pfae import fill_contrato_pfae

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


DATOS = {
    "nombre_pf": "HOLSCHNEIDER DEL VILLAR ANDREA MARIA",
    "curp": "HOVA891213MNELLN08",
    "nombre_comercial": "Andrea Holschneider",
    "rfc": "HOVA891213DL9",
    "linea_credito": "$100,000.00 M.N.",
    "mensualidad": "$2,000.00 M.N.",
    "firma_nombre": "ANDREA MARIA HOLSCHNEIDER DEL VILLAR",
}


def test_nombre_de_firma_va_debajo_de_la_linea_junto_a_nombre_sin_invadir_la_columna_derecha():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "contrato_pfae.pdf")
        fill_contrato_pfae(DATOS, out)
        with pdfplumber.open(out) as pdf:
            p = pdf.pages[0]
            nombre = next((w for w in p.extract_words()
                          if w["text"] == "ANDREA" and w["x0"] < 300 and w["top"] > 600), None)
            check(nombre is not None, "el nombre de firma debe aparecer en la zona de firma de la página 1")
            if nombre is None:
                return

            etiqueta = next(w for w in p.extract_words() if w["text"] == "Nombre:")
            lineas = [r for r in p.rects if r["height"] < 1 and r["x0"] < 300
                     and 600 < r["top"] < 792]
            check(len(lineas) == 1, "debe haber una sola línea de firma del cliente en esa zona")
            linea = lineas[0]

            check(nombre["top"] > linea["bottom"],
                  "el nombre debe quedar debajo de la línea de firma, no arriba de ella")
            check(abs(nombre["top"] - etiqueta["top"]) < 3,
                  "el nombre debe ir en el mismo renglón que la etiqueta 'Nombre:' "
                  "(top nombre=%.1f, top etiqueta=%.1f)" % (nombre["top"], etiqueta["top"]))
            check(nombre["x0"] > etiqueta["x1"],
                  "el nombre debe ir después de la etiqueta 'Nombre:', no encimado con ella")

            check(nombre["x1"] < 315,
                  "el nombre no debe extenderse hacia la columna derecha (firma de Nea)")


def main():
    test_nombre_de_firma_va_debajo_de_la_linea_junto_a_nombre_sin_invadir_la_columna_derecha()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
