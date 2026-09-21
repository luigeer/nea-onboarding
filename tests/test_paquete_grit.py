# -*- coding: utf-8 -*-
"""
Pruebas de generar_paquete.py: los tres documentos de Grit Mobility deben
estar en el catálogo (con sufijo de archivo propio, distinto al de los
documentos de Nea) y tener sus firmantes correctos — el cliente firma los
tres, y Luis Gómez Montijano firma por Grit Mobility en el contrato y como
Responsable de Cumplimiento en el Beneficiario Controlador.

Todos los datos son inventados.

Se corre con:
    python tests/test_paquete_grit.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generadores"))

from generar_paquete import CATALOGO, _firmantes
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
    e["representante_legal"]["validado"]["nombre"] = "JUAN PEREZ GARCIA"
    e["beneficiarios_controladores"] = [{"nombre": "CARLOS RUIZ"}]
    return e


def test_catalogo_trae_los_tres_documentos_de_grit_con_sufijo_propio():
    for clave in ("grit_contrato", "grit_pld_pm", "grit_pld_pf", "grit_beneficiario_controlador"):
        check(clave in CATALOGO, "%s debe estar en CATALOGO" % clave)

    sufijos_nea = {CATALOGO[c][0] for c in ("contrato", "pld_pm", "pld_pf", "beneficiario_controlador")}
    sufijos_grit = {CATALOGO[c][0] for c in
                    ("grit_contrato", "grit_pld_pm", "grit_pld_pf", "grit_beneficiario_controlador")}
    check(not (sufijos_nea & sufijos_grit),
          "los sufijos de archivo de Grit no deben chocar con los de Nea (%r vs %r)"
          % (sufijos_nea, sufijos_grit))


def test_cliente_firma_el_contrato_de_grit_y_luis_gomez_firma_por_grit():
    exp = persona_moral()
    firmantes = _firmantes("grit_contrato", exp)
    roles = [f["rol"] for f in firmantes]
    check("cliente" in roles, "el cliente debe firmar el Contrato de Prestación de Servicios de Grit")
    nombres = [f["nombre"] for f in firmantes]
    check("Luis Gómez Montijano" in nombres,
          "Luis Gómez Montijano debe firmar por Grit Mobility en su Contrato de Prestación de Servicios")


def test_cliente_y_luis_gomez_firman_el_bc_de_grit():
    exp = persona_moral()
    firmantes = _firmantes("grit_beneficiario_controlador", exp)
    check(any(f["rol"] == "cliente" for f in firmantes),
          "el cliente debe firmar el Beneficiario Controlador de Grit")
    check(any(f["nombre"] == "Luis Gómez Montijano" for f in firmantes),
          "Luis Gómez Montijano debe firmar como Responsable de Cumplimiento de Grit Mobility")


def test_solo_cliente_firma_el_pld_de_grit():
    exp = persona_moral()
    firmantes = _firmantes("grit_pld_pm", exp)
    check(len(firmantes) == 1 and firmantes[0]["rol"] == "cliente",
          "el PLD de Grit, igual que el de Nea, solo lo firma el cliente")


def main():
    test_catalogo_trae_los_tres_documentos_de_grit_con_sufijo_propio()
    test_cliente_firma_el_contrato_de_grit_y_luis_gomez_firma_por_grit()
    test_cliente_y_luis_gomez_firman_el_bc_de_grit()
    test_solo_cliente_firma_el_pld_de_grit()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
