# -*- coding: utf-8 -*-
"""
Pruebas de los adaptadores grit_pld_pm / grit_pld_pf / grit_beneficiario_controlador:
deben traducir el MISMO expediente que sus equivalentes de Nea, pero dirigidos a
Grit Mobility, S.A. de C.V. como sujeto obligado, con la actividad vulnerable
"Emisión de tarjetas prepagadas de gasolina" y Luis Gómez Montijano como
Responsable de Cumplimiento.

Todos los datos son inventados.

Se corre con:
    python tests/test_adaptadores_grit.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adaptadores import ADAPTADORES
from schema_expediente import expediente_vacio

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def persona_moral():
    e = expediente_vacio()
    e["folio"] = "T-01"
    e["tipo_cliente"] = "persona_moral"
    e["cliente"]["validado"]["razon_social"] = "EJEMPLO INDUSTRIAL, S.A. DE C.V."
    e["representante_legal"]["validado"]["nombre"] = "JUAN PEREZ GARCIA"
    e["beneficiarios_controladores"] = [{"nombre": "CARLOS RUIZ"}]
    return e


def persona_fisica():
    e = expediente_vacio()
    e["folio"] = "T-02"
    e["tipo_cliente"] = "pfae"
    e["representante_legal"]["validado"]["nombre"] = "JUAN PEREZ GARCIA"
    return e


def test_grit_pld_pm_usa_el_mismo_cliente_con_sujeto_obligado_de_grit():
    exp = persona_moral()
    nea = ADAPTADORES["pld_pm"](exp)
    grit = ADAPTADORES["grit_pld_pm"](exp)
    check(grit["razon_social"] == nea["razon_social"],
          "grit_pld_pm debe traducir los mismos datos del cliente que pld_pm")
    check(grit["sujeto_obligado_nombre"] == "GRIT MOBILITY, S.A. DE C.V.",
          "grit_pld_pm debe dirigirse a Grit Mobility, S.A. de C.V.")
    check(grit["actividad_vulnerable"] == "Emisión de tarjetas prepagadas de gasolina",
          "grit_pld_pm debe declarar la actividad vulnerable de Grit Mobility")


def test_grit_pld_pf_usa_el_mismo_cliente_con_sujeto_obligado_de_grit():
    exp = persona_fisica()
    nea = ADAPTADORES["pld_pf"](exp)
    grit = ADAPTADORES["grit_pld_pf"](exp)
    check(grit["nombre_completo"] == nea["nombre_completo"],
          "grit_pld_pf debe traducir los mismos datos del cliente que pld_pf")
    check(grit["sujeto_obligado_nombre"] == "GRIT MOBILITY, S.A. DE C.V.",
          "grit_pld_pf debe dirigirse a Grit Mobility, S.A. de C.V.")
    check(grit["actividad_vulnerable"] == "Emisión de tarjetas prepagadas de gasolina",
          "grit_pld_pf debe declarar la actividad vulnerable de Grit Mobility")


def test_grit_contrato_traduce_cliente_y_condiciones_comerciales():
    exp = persona_moral()
    exp["cliente"]["validado"]["rfc"] = "EJE200803A2A"
    exp["cliente"]["validado"]["actividad_economica"] = "Transporte de carga"
    exp["grit_monedero"]["modelo_negocio"] = "prepago"
    exp["grit_monedero"]["comision"] = "1.5%"
    grit = ADAPTADORES["grit_contrato"](exp)
    check(grit["tipo_persona"] == "moral", "grit_contrato debe traducir tipo_cliente a tipo_persona")
    check(grit["razon_social"] == "EJEMPLO INDUSTRIAL, S.A. DE C.V.",
          "grit_contrato debe traer la razón social del cliente")
    check(grit["rfc_empresa"] == "EJE200803A2A", "grit_contrato debe traer el RFC del cliente")
    check(grit["modelo_negocio"] == "CLIENTE PREPAGO",
          "grit_contrato debe traducir modelo_negocio 'prepago' a la leyenda del contrato")
    check(grit["comision"] == "1.5%", "grit_contrato debe traer la comisión pactada")
    check(grit["representantes"][0]["nombre"] == "PEREZ GARCIA JUAN",
          "grit_contrato debe traer al representante legal como primer firmante, "
          "en el mismo orden apellidos-primero que usan los demás generadores")


def test_grit_beneficiario_usa_el_mismo_cliente_con_responsable_de_grit():
    exp = persona_moral()
    nea = ADAPTADORES["beneficiario_controlador"](exp)
    grit = ADAPTADORES["grit_beneficiario_controlador"](exp)
    check(grit["cliente"]["razon_social"] == nea["cliente"]["razon_social"],
          "grit_beneficiario_controlador debe traducir los mismos datos del cliente")
    check(grit["sujeto_obligado"] == "Grit Mobility, S.A. de C.V.",
          "grit_beneficiario_controlador debe dirigirse a Grit Mobility, S.A. de C.V.")
    check(grit["responsable_cumplimiento"]["nombre"] == "Luis Gómez Montijano",
          "el Responsable de Cumplimiento de Grit Mobility es Luis Gómez Montijano")


def test_beneficiario_de_nea_sin_excepcion_usa_al_oficial_de_grit_payment():
    exp = persona_moral()
    exp["cumplimiento"]["responsable"] = None
    nea = ADAPTADORES["beneficiario_controlador"](exp)
    check(nea["responsable_cumplimiento"].get("nombre") == "Marcos Siqueiros Ballesteros",
          "sin excepción capturada, el Formato BC de Nea lleva al Oficial de "
          "Cumplimiento de Grit Payment, no queda en blanco")
    grit = ADAPTADORES["grit_beneficiario_controlador"](exp)
    check(grit["responsable_cumplimiento"]["nombre"] == "Luis Gómez Montijano",
          "y el de Grit Mobility sigue llevando a Luis")


def main():
    test_grit_pld_pm_usa_el_mismo_cliente_con_sujeto_obligado_de_grit()
    test_grit_pld_pf_usa_el_mismo_cliente_con_sujeto_obligado_de_grit()
    test_grit_contrato_traduce_cliente_y_condiciones_comerciales()
    test_grit_beneficiario_usa_el_mismo_cliente_con_responsable_de_grit()
    test_beneficiario_de_nea_sin_excepcion_usa_al_oficial_de_grit_payment()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
