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


def test_srl_dice_partes_sociales_y_socios():
    """Caso real (TEAK-01): una S. de R.L. no tiene acciones sino partes sociales."""
    e = expediente()
    e["cliente"]["validado"]["regimen_capital"] =         "SOCIEDAD DE RESPONSABILIDAD LIMITADA DE CAPITAL VARIABLE"
    e["constitucion"]["acciones"] = 2
    e["beneficiarios_controladores"][0]["desglose_acciones"] = "1 parte social de 2"
    e["estructura_accionaria"] = [
        {"accionista": "SOCIO UNO", "acciones": 1, "importe": 24750.0, "porcentaje": 99.0},
        {"accionista": "SOCIO DOS", "acciones": 1, "importe": 250.0, "porcentaje": 1.0}]
    for clave in ("beneficiario_controlador", "grit_beneficiario_controlador"):
        t = texto(clave, e)
        check("Partes sociales: 2" in t, "%s: 'Partes sociales: 2' en el apartado I" % clave)
        check("Desglose de partes sociales" in t, "%s: 'Desglose de partes sociales'" % clave)
        check("Socio Partes sociales" in t, "%s: la tabla dice Socio / Partes sociales" % clave)
        check("ESTRUCTURA DE CAPITAL" in t, "%s: el apartado III no dice 'accionaria'" % clave)
        check("Acciones" not in t and "Accionista" not in t and "ACCIONARIA" not in t,
              "%s: no quedan 'Acciones', 'Accionista' ni 'ACCIONARIA'" % clave)


def test_sociedad_anonima_sigue_diciendo_acciones():
    e = expediente()
    e["cliente"]["validado"]["regimen_capital"] = "SOCIEDAD ANONIMA DE CAPITAL VARIABLE"
    e["constitucion"]["acciones"] = 50000
    e["estructura_accionaria"] = [{"accionista": "X", "acciones": 50000,
                                   "importe": 50000.0, "porcentaje": 100.0}]
    t = texto("beneficiario_controlador", e)
    check("Acciones: 50000" in t and "Accionista Acciones" in t
          and "ESTRUCTURA ACCIONARIA" in t,
          "en una S.A. el formato sigue con Acciones / Accionista")


def test_la_ficha_muestra_el_numero_de_identificacion():
    """Los expedientes guardan identificacion.numero; el formato solo leía 'dato'
    y el número no salía en ningún BC (TEAK-01, ASIAT-01, INTEGRA-01...)."""
    e = expediente()
    e["beneficiarios_controladores"][0]["identificacion"] = {
        "tipo": "INE - Credencial para votar", "numero": "2519039700",
        "vigencia": "31/12/2033"}
    t = texto("grit_beneficiario_controlador", e)
    check("2519039700" in t, "el número de la identificación aparece en el BC")


def main():
    test_la_declaracion_adicional_sale_en_ambos_formatos()
    test_sin_declaracion_adicional_quedan_las_tres_fijas()
    test_srl_dice_partes_sociales_y_socios()
    test_sociedad_anonima_sigue_diciendo_acciones()
    test_la_ficha_muestra_el_numero_de_identificacion()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
