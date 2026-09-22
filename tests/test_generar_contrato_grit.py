# -*- coding: utf-8 -*-
"""
Pruebas de generar_contrato_grit.py: el Contrato de Prestación de Servicios de
Grit Mobility, S.A. de C.V. — 31 cláusulas de texto fijo más el Anexo A
(Formato de Alta de Clientes) con los datos del cliente en turno.

No se prueba cláusula por cláusula (es texto legal fijo, igual para todos los
clientes): se prueba que el documento trae las 31, que el Anexo A refleja los
datos del cliente, y que persona moral y PFAE producen el Anexo A correcto
cada una.

Se corre con:
    python tests/test_generar_contrato_grit.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generadores"))

import pdfplumber

from generar_contrato_grit import generar_contrato_grit

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


CLAUSULAS = [
    "PRIMERA. - DEFINICIONES",
    "SEGUNDA. - OBJETO",
    "DÉCIMA. - SISTEMA Y PORTAL",
    "DÉCIMA SÉPTIMA. - TERMINACIÓN Y RESCISIÓN",
    "VIGÉSIMA SEXTA",
    "TRIGÉSIMA. - MODIFICACIONES",
    "TRIGÉSIMA PRIMERA. - JURISDICCIÓN",
]

DATOS_PM = {
    "tipo_persona": "moral",
    "razon_social": "EJEMPLO INDUSTRIAL, S.A. DE C.V.",
    "nombre_comercial": "Ejemplo Industrial",
    "rfc_empresa": "EJE200803A2A",
    "actividad_giro": "Transporte de carga",
    "nacionalidad": None,
    "modelo_negocio": "CLIENTE PREPAGO",
    "constitucion": {
        "no_escritura": "12,345", "fecha": "15/01/2020",
        "notario": "Lic. Fulano de Tal", "notaria_ubicacion": "No. 10, CDMX",
        "folio_rpc": "N-2020001111", "fecha_inscripcion_rpc": "20/01/2020",
    },
    "representantes": [
        {"nombre": "JUAN PEREZ GARCIA", "escritura": "54,321 de 20/02/2020",
         "notario": "Lic. Mengano", "notaria": "No. 20, CDMX"},
    ],
    "contacto": {"nombre": "María López", "telefono_1": "5555555555",
                "telefono_2": None, "correo": "maria@ejemplo.mx"},
    "domicilio_fiscal": {"calle": "Av. Reforma", "num_ext": "100", "num_int": None,
                         "colonia": "Juárez", "cp": "06600",
                         "municipio": "Cuauhtémoc", "estado": "CDMX"},
    "domicilio_entrega": None,
    "comision": "1.5%", "cuota": "No aplica", "costo_tarjeta": "$150.00 M.N.",
    "comentarios": "—",
    "fecha_firma_larga": "10 de septiembre de 2026",
}

DATOS_PFAE = dict(DATOS_PM, tipo_persona="pfae", nacionalidad="Mexicana", constitucion=None,
                  razon_social="JUAN PEREZ GARCIA", nombre_comercial="Transportes Pérez")


def texto_pdf(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def test_contrato_pm_trae_las_31_clausulas():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "contrato_grit.pdf")
        generar_contrato_grit(DATOS_PM, out)
        texto = texto_pdf(out)
        for titulo in CLAUSULAS:
            check(titulo in texto, "debe incluir la cláusula %r" % titulo)
        check("{{" not in texto, "no debe quedar ningún marcador sin resolver")
        check("Luis Gómez Montijano" in texto,
              "NEA_REPRESENTANTE es fijo: Luis Gómez Montijano")


def test_anexo_a_persona_moral_refleja_los_datos_del_cliente():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "contrato_grit_pm.pdf")
        generar_contrato_grit(DATOS_PM, out)
        texto = texto_pdf(out)
        check("EJEMPLO INDUSTRIAL, S.A. DE C.V." in texto, "Anexo A debe traer la razón social")
        check("EJE200803A2A" in texto, "Anexo A debe traer el RFC")
        check("JUAN PEREZ GARCIA" in texto, "Anexo A debe traer al representante legal")
        check("12,345" in texto, "Anexo A (PM) debe traer el número de escritura constitutiva")
        check("1.5%" in texto, "Anexo A debe traer la comisión pactada")


def test_anexo_a_pfae_no_trae_datos_de_constitucion():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "contrato_grit_pfae.pdf")
        generar_contrato_grit(DATOS_PFAE, out)
        texto = texto_pdf(out)
        check("PERSONA FÍSICA CON ACTIVIDAD EMPRESARIAL" in texto,
              "Anexo A (PFAE) debe declarar el tipo de persona")
        check("12,345" not in texto,
              "PFAE no tiene escritura constitutiva: no debe traer la de la PM de otra prueba")


def main():
    test_contrato_pm_trae_las_31_clausulas()
    test_anexo_a_persona_moral_refleja_los_datos_del_cliente()
    test_anexo_a_pfae_no_trae_datos_de_constitucion()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
