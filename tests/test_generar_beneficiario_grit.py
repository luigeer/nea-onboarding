# -*- coding: utf-8 -*-
"""
Pruebas de generar_beneficiario.py: el "Sujeto Obligado" que aparece en el
encabezado, el pie de página y el autor del PDF debe poder sobreescribirse por
datos, para poder emitir el mismo formato a nombre de Grit Mobility en vez de
Nea/Grit Payment Solutions.

Se corre con:
    python tests/test_generar_beneficiario_grit.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generadores"))

import pdfplumber

from generar_beneficiario import generar_beneficiario

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


DATOS_BASE = {
    "cliente": {"razon_social": "EMPRESA, S.A. DE C.V.", "rfc": "EMP120831AB1"},
    "beneficiarios": [{"nombre": "juan perez garcia", "cargo": "Accionista"}],
    "responsable_cumplimiento": {"nombre": "Marcos Siqueiros Ballesteros"},
}


def texto_pdf(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def test_sujeto_obligado_por_defecto_es_nea():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "bc.pdf")
        generar_beneficiario(dict(DATOS_BASE), out)
        texto = texto_pdf(out)
        check("Grit Payment Solutions" in texto,
              "sin sujeto_obligado en los datos, el encabezado sigue siendo el de Nea")


def test_sujeto_obligado_personalizado_para_grit_mobility():
    datos = dict(DATOS_BASE)
    datos["sujeto_obligado"] = "Grit Mobility, S.A. de C.V."
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "bc_grit.pdf")
        generar_beneficiario(datos, out)
        texto = texto_pdf(out)
        check("Grit Mobility, S.A. de C.V." in texto,
              "con sujeto_obligado en los datos, el encabezado y pie deben decir Grit Mobility")
        check("Grit Payment Solutions" not in texto,
              "el formato de Grit Mobility no debe dejar restos del sujeto obligado de Nea")


def main():
    test_sujeto_obligado_por_defecto_es_nea()
    test_sujeto_obligado_personalizado_para_grit_mobility()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
