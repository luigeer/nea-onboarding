# -*- coding: utf-8 -*-
"""
Pruebas de la matriz de documentos: a partir de ahora, todo cliente que reciba
el PLD y/o el Beneficiario Controlador de Nea recibe también su equivalente a
nombre de Grit Mobility, más el Contrato de Prestación de Servicios de Grit
Mobility — los use o no.

Todos los datos son inventados.

Se corre con:
    python tests/test_documentos_grit.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema_expediente import documentos_aplicables, expediente_vacio

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def persona_moral(**cambios):
    e = expediente_vacio()
    e["folio"] = "T-01"
    e["tipo_cliente"] = "persona_moral"
    e["beneficiarios_controladores"] = [{"nombre": "CARLOS RUIZ"}]
    e["estructura_accionaria"] = [{"nombre": "CARLOS RUIZ", "porcentaje": 100.0}]
    e.update(cambios)
    return e


def persona_fisica(**cambios):
    e = expediente_vacio()
    e["folio"] = "T-02"
    e["tipo_cliente"] = "pfae"
    e.update(cambios)
    return e


def test_expediente_vacio_trae_condiciones_comerciales_de_grit():
    e = expediente_vacio()
    grit = e["grit_monedero"]
    check(set(["modelo_negocio", "comision", "cuota", "costo_tarjeta",
               "comentarios", "domicilio_entrega"]) <= set(grit),
          "expediente_vacio debe traer grit_monedero con los campos comerciales "
          "que exige el Contrato de Prestación de Servicios")
    check(set(["calle", "num_ext", "num_int", "colonia", "cp", "municipio",
               "estado"]) <= set(grit["domicilio_entrega"]),
          "grit_monedero.domicilio_entrega debe tener la misma forma que un domicilio")


def test_persona_moral_recibe_contrato_pld_y_bc_de_grit():
    docs = documentos_aplicables(persona_moral())
    check("grit_contrato" in docs,
          "el Contrato de Prestación de Servicios de Grit Mobility se agrega siempre")
    check("grit_pld_pm" in docs,
          "si aplica pld_pm, también debe aplicar grit_pld_pm")
    check("grit_beneficiario_controlador" in docs,
          "si aplica beneficiario_controlador, también debe aplicar grit_beneficiario_controlador")


def test_persona_fisica_recibe_contrato_y_pld_de_grit_sin_bc():
    docs = documentos_aplicables(persona_fisica())
    check("grit_contrato" in docs,
          "PFAE: el Contrato de Prestación de Servicios de Grit Mobility se agrega siempre")
    check("grit_pld_pf" in docs,
          "PFAE: si aplica pld_pf, también debe aplicar grit_pld_pf")
    check("grit_beneficiario_controlador" not in docs,
          "PFAE: no hay beneficiario_controlador de Nea, tampoco debe haber el de Grit")


def main():
    test_expediente_vacio_trae_condiciones_comerciales_de_grit()
    test_persona_moral_recibe_contrato_pld_y_bc_de_grit()
    test_persona_fisica_recibe_contrato_y_pld_de_grit_sin_bc()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
