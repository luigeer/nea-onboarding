# -*- coding: utf-8 -*-
"""Declaraciones adicionales en el formato de beneficiario controlador.

Caso real (TEAK-01): el 99% de Teakhaus México es de Teakhaus, LLC, cuyos
socios no constan en el acta. El beneficiario se determina por control
efectivo, y el representante declara bajo protesta que la LLC no tiene ningún
socio con 25% o más. Esa declaración tiene que quedar en el formato que firma,
junto a las declaraciones fijas, no en una nota aparte que nadie firma.

Se corre con:
    python tests/test_declaraciones_bc.py
"""

import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "generadores"))

import pdfplumber

from adaptadores import ADAPTADORES
from generar_beneficiario import generar_beneficiario
from schema_expediente import expediente_vacio

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


DECL = ("Que TEAKHAUS, LLC no tiene ningún socio o accionista que detente, directa o "
        "indirectamente, el 25% o más de su capital social.")


def expediente():
    e = expediente_vacio()
    e["folio"] = "T-01"
    e["tipo_cliente"] = "persona_moral"
    e["cliente"]["validado"]["razon_social"] = "EJEMPLO, S. de R.L. de C.V."
    e["representante_legal"]["validado"]["nombre"] = "JUAN PEREZ GARCIA"
    e["beneficiarios_controladores"] = [{"nombre": "ANA LOPEZ"}]
    e["criterio_identificacion"] = "control_efectivo"
    return e


def texto(clave, exp):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "bc.pdf")
        generar_beneficiario(ADAPTADORES[clave](exp), out)
        with pdfplumber.open(out) as pdf:
            return " ".join((p.extract_text() or "").replace("\n", " ") for p in pdf.pages)


def test_la_declaracion_adicional_sale_en_ambos_formatos():
    e = expediente()
    e["bc_declaraciones_adicionales"] = [DECL]
    for clave in ("beneficiario_controlador", "grit_beneficiario_controlador"):
        t = texto(clave, e)
        check("no tiene ningún socio o accionista que detente" in t,
              "%s lleva la declaración adicional" % clave)
        check("4. Que TEAKHAUS, LLC" in t,
              "%s la numera después de las tres fijas" % clave)


def test_sin_declaracion_adicional_quedan_las_tres_fijas():
    t = texto("beneficiario_controlador", expediente())
    check("3. Que ha puesto a disposición" in t and "4. " not in t.split("DECLARACIONES")[-1]
          .split("AVISO DE PRIVACIDAD")[0],
          "sin adicionales, el apartado IV tiene solo las tres declaraciones fijas")


def main():
    test_la_declaracion_adicional_sale_en_ambos_formatos()
    test_sin_declaracion_adicional_quedan_las_tres_fijas()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
