# -*- coding: utf-8 -*-
"""Paquete solo de Grit Mobility: el monedero sin la tarjeta de crédito de Nea.

Es el espejo de `sin_grit_mobility`. Hay clientes que solo contratan el monedero
de combustible (Marcos Siqueiros, Teakhaus México): no hay línea de crédito, así
que no hay carátula de Nea Card, ni PLD ni BC dirigidos a Grit Payment, ni
estados de cuenta que pedir. Lo que sí firman son los documentos de Grit
Mobility, y esos siguen exigiendo los datos del Anexo A.

Como toda salida de las reglas normales, cuenta solo si dice por qué y quién lo
decidió; a medio llenar no quita nada y la compuerta lo reporta.

Se corre con:
    python tests/test_solo_grit_mobility.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema_expediente import compuertas_generacion, documentos_aplicables, expediente_vacio

fallas = []


def check(cond, msg):
    print(("  ok   " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def hay(lista, texto):
    return any(texto in f for f in lista)


SOLO = {"justificacion": "Solo contrata el monedero de combustible.",
        "decidido_por": "Luis Gomez", "fecha": "2026-10-14"}


def moral_solo_grit():
    """Persona moral con todo lo de Grit Mobility y nada del crédito de Nea."""
    e = expediente_vacio()
    e["folio"] = "PRUEBA-01"
    e["tipo_cliente"] = "persona_moral"
    e["constitucion"].update({"inscripcion_rpc": "N-1", "fecha_inscripcion_rpc": "2020-02-20"})
    e["representante_legal"]["validado"].update({
        "nombre": "ANA PEREZ",
        "poder": {"escritura": "1", "notario": "Lic. X", "notaria": "No. 1"},
    })
    e["grit_monedero"].update({"modelo_negocio": "prepago", "comision": "1.25%",
                               "cuota": 0, "costo_tarjeta": 0})
    e["beneficiarios_controladores"] = [{"nombre": "ANA PEREZ"}]
    e["cumplimiento"]["bc_firmado_por"] = "Luis Gomez"
    e["criterio_identificacion"] = "participacion"
    e["solo_grit_mobility"] = dict(SOLO)
    return e


def pfae_solo_grit():
    e = expediente_vacio()
    e["folio"] = "PRUEBA-02"
    e["tipo_cliente"] = "pfae"
    e["representante_legal"]["validado"].update({
        "nombre": "JUAN PEREZ", "curp": "PEPJ800101HDFRRN09", "rfc": "PEPJ800101AB1",
        "fecha_nacimiento": "1980-01-01", "pais_nacimiento": "México",
        "pais_nacionalidad": "México",
        "identificacion": {"tipo": "INE", "numero": "123", "autoridad_emisora": "INE",
                           "pais_emisor": "México", "vigencia": None},
    })
    e["grit_monedero"].update({"modelo_negocio": "prepago", "comision": "1.25%",
                               "cuota": 0, "costo_tarjeta": 0})
    e["solo_grit_mobility"] = dict(SOLO)
    return e


def test_persona_moral_solo_lleva_documentos_de_grit_mobility():
    docs = documentos_aplicables(moral_solo_grit())
    check(docs == ["grit_contrato", "grit_pld_pm", "grit_beneficiario_controlador"],
          "persona moral solo Grit: contrato, PLD y BC de Grit Mobility (salió %r)" % docs)


def test_pfae_solo_lleva_contrato_y_pld_de_grit_mobility():
    docs = documentos_aplicables(pfae_solo_grit())
    check(docs == ["grit_contrato", "grit_pld_pf"],
          "PFAE solo Grit: contrato y PLD de Grit Mobility (salió %r)" % docs)


def test_sin_flags_de_credito_no_se_cuelan_documentos_de_nea():
    e = moral_solo_grit()
    e["flags"]["obligado_solidario"] = True
    e["obligado_solidario"]["tipo"] = "persona_moral"
    e["flags"]["buro_en_paquete"] = True
    docs = documentos_aplicables(e)
    check(not any(d in docs for d in ("adenda_os_pm", "autorizacion_buro", "contrato")),
          "solo Grit: ni adenda, ni buró, ni carátula de Nea (salió %r)" % docs)


def test_solo_grit_no_exige_linea_ni_estados_ni_titulos_de_credito():
    f = compuertas_generacion(moral_solo_grit())
    check(f == [], "persona moral solo Grit completa se puede generar: %r" % f)
    f = compuertas_generacion(pfae_solo_grit())
    check(f == [], "PFAE solo Grit completa se puede generar: %r" % f)


def test_solo_grit_sigue_exigiendo_el_anexo_a():
    e = moral_solo_grit()
    e["grit_monedero"]["modelo_negocio"] = None
    check(hay(compuertas_generacion(e), "Grit: falta grit_monedero.modelo_negocio"),
          "solo Grit sin modelo de negocio no se genera")


def test_solo_grit_sigue_exigiendo_firmante_validado():
    e = moral_solo_grit()
    e["representante_legal"]["validado"]["nombre"] = None
    check(hay(compuertas_generacion(e), "Representante legal sin validar"),
          "solo Grit sin representante validado no se genera")


def test_solo_grit_incompleto_no_quita_nada_y_se_reporta():
    e = moral_solo_grit()
    e["solo_grit_mobility"]["decidido_por"] = None
    check("contrato" in documentos_aplicables(e),
          "sin nombre de quien decidió, el paquete sigue siendo el normal")
    check(hay(compuertas_generacion(e), "solo Grit Mobility"),
          "una decisión de solo Grit incompleta se reporta como falla")


def test_solo_y_sin_grit_a_la_vez_es_contradiccion():
    e = moral_solo_grit()
    e["sin_grit_mobility"] = dict(SOLO)
    check(hay(compuertas_generacion(e), "contradic"),
          "solo Grit y sin Grit a la vez se reporta como contradicción")


def test_el_validador_no_pide_estados_de_cuenta_con_solo_grit():
    import validador
    pide = any(h["asunto"] == "Faltan estados de cuenta"
               for h in validador.revisar(moral_solo_grit()).hallazgos)
    check(not pide, "con solo Grit vigente, el validador no pide estados de cuenta")


def _pide_buro(exp):
    import validador
    return any("buró" in h["asunto"] for h in validador.revisar(exp).hallazgos)


def test_sin_modelo_de_riesgo_no_se_pide_autorizacion_de_buro():
    """Caso real (TEAK-01): ya es cliente de Grit Payment y solo contrata el
    monedero; no hay modelo que alimentar, así que tampoco buró que consultar."""
    check(not _pide_buro(moral_solo_grit()),
          "con solo Grit vigente, el validador no pide autorización de buró")
    check(not _pide_buro(pfae_solo_grit()),
          "PFAE con solo Grit vigente: tampoco pide autorización de buró")
    con_excepcion = moral_solo_grit()
    con_excepcion.pop("solo_grit_mobility")
    con_excepcion["credito"]["autorizada"].update({"linea": 50000.0, "autorizada_por": "Luis"})
    con_excepcion["credito"]["excepcion_riesgo"] = {
        "motivo": "socio_comercial", "justificacion": "Socio comercial; sin análisis financiero.",
        "autorizada_por": "Luis Gomez", "fecha": "2026-10-14"}
    check(not _pide_buro(con_excepcion),
          "con excepción de riesgo vigente, el validador no pide autorización de buró")
    normal = moral_solo_grit()
    normal.pop("solo_grit_mobility")
    check(_pide_buro(normal),
          "sin excepción y con crédito, el validador sigue pidiendo autorización de buró")


def main():
    test_persona_moral_solo_lleva_documentos_de_grit_mobility()
    test_pfae_solo_lleva_contrato_y_pld_de_grit_mobility()
    test_sin_flags_de_credito_no_se_cuelan_documentos_de_nea()
    test_solo_grit_no_exige_linea_ni_estados_ni_titulos_de_credito()
    test_solo_grit_sigue_exigiendo_el_anexo_a()
    test_solo_grit_sigue_exigiendo_firmante_validado()
    test_solo_grit_incompleto_no_quita_nada_y_se_reporta()
    test_solo_y_sin_grit_a_la_vez_es_contradiccion()
    test_el_validador_no_pide_estados_de_cuenta_con_solo_grit()
    test_sin_modelo_de_riesgo_no_se_pide_autorizacion_de_buro()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
