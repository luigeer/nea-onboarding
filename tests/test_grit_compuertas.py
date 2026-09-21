# -*- coding: utf-8 -*-
"""Datos indispensables del Anexo A antes de generar el paquete de Grit."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adaptadores import ADAPTADORES
from schema_expediente import compuertas_generacion, compuertas_grit, expediente_vacio


def check(cond, msg):
    print(("  ok   " if cond else "FALLA ") + msg)
    if not cond:
        raise AssertionError(msg)


def moral_completa():
    e = expediente_vacio()
    e["tipo_cliente"] = "persona_moral"
    e["constitucion"].update({
        "fecha": "2020-01-15", "inscripcion_rpc": "N-123",
        "fecha_inscripcion_rpc": "2020-02-20",
    })
    e["representante_legal"]["validado"].update({
        "nombre": "ANA PEREZ", "poder": {
            "escritura": "123 de 2021", "notario": "Lic. Ejemplo",
            "notaria": "No. 8, CDMX",
        },
    })
    e["grit_monedero"].update({
        "modelo_negocio": "prepago", "comision": "1.5%",
        "cuota": "No aplica", "costo_tarjeta": "$150",
    })
    return e


e = moral_completa()
check(compuertas_grit(e) == [], "un Anexo A completo supera las compuertas")
d = ADAPTADORES["grit_contrato"](e)
check(d["constitucion"]["fecha_inscripcion_rpc"] == "20/02/2020",
      "la fecha de inscripción RPC sale de su propio campo")
check(d["constitucion"]["fecha_inscripcion_rpc"] != d["constitucion"]["fecha"],
      "la inscripción RPC no se sustituye por la constitución")
check(d["representantes"][0]["escritura"] == "123 de 2021",
      "el poder del representante llega al Anexo A")
check(d["representantes"][0]["notario"] == "Lic. Ejemplo",
      "el notario del poder llega al Anexo A")

for campo in ("modelo_negocio", "comision", "cuota", "costo_tarjeta"):
    incompleto = moral_completa()
    incompleto["grit_monedero"][campo] = None
    check(any(campo in f for f in compuertas_grit(incompleto)),
          "falta de %s bloquea generación" % campo)
    check(any(campo in f for f in compuertas_generacion(incompleto)),
          "la compuerta general bloquea %s" % campo)

sin_fecha = moral_completa()
sin_fecha["constitucion"]["fecha_inscripcion_rpc"] = None
check(any("fecha_inscripcion_rpc" in f for f in compuertas_grit(sin_fecha)),
      "sin fecha RPC no se inventa una fecha")

fecha_invalida = moral_completa()
fecha_invalida["constitucion"]["fecha_inscripcion_rpc"] = "2020-02-30"
check(any("fecha_inscripcion_rpc" in f for f in compuertas_grit(fecha_invalida)),
      "una fecha RPC imposible no se imprime en el contrato")

sin_poder = moral_completa()
sin_poder["representante_legal"]["validado"]["poder"]["notaria"] = None
check(any("poder.notaria" in f for f in compuertas_grit(sin_poder)),
      "sin notaría del poder no se genera el contrato")

poder_en_blanco = moral_completa()
poder_en_blanco["representante_legal"]["validado"]["poder"]["notaria"] = "   "
check(any("poder.notaria" in f for f in compuertas_grit(poder_en_blanco)),
      "una notaría en blanco no satisface la compuerta")

con_cofirmante = moral_completa()
con_cofirmante["cofirmantes"] = [{"nombre": "JUAN LOPEZ"}]
check(any("cofirmantes[0].poder" in f for f in compuertas_grit(con_cofirmante)),
      "cada cofirmante necesita datos de su poder")
con_cofirmante["cofirmantes"][0]["poder"] = {
    "escritura": "789 de 2022", "notario": "Lic. Otro", "notaria": "No. 9, CDMX",
}
check(compuertas_grit(con_cofirmante) == [],
      "el poder completo del cofirmante satisface la compuerta")
check(ADAPTADORES["grit_contrato"](con_cofirmante)["representantes"][1]["escritura"]
      == "789 de 2022", "el poder del cofirmante llega al Anexo A")

pfae = expediente_vacio()
pfae["tipo_cliente"] = "pfae"
pfae["grit_monedero"].update(e["grit_monedero"])
check(compuertas_grit(pfae) == [],
      "a una persona física no se le exigen RPC ni poderes")
