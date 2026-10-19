# -*- coding: utf-8 -*-
"""Excepciones formales: línea sin modelo de riesgo, y paquete sin Grit Mobility.

Las dos existen para casos reales —un socio comercial al que no se le pide
información financiera, y un cliente respaldado por un obligado solidario que ya
tiene una línea mayor autorizada; y un cliente que solo firma con Grit Payment—.
Lo que se prueba aquí es que la salida exista **y** que no se pueda tomar sin
dejar escrito por qué y quién respondió por ello.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema_expediente import compuertas_generacion, documentos_aplicables, expediente_vacio


def check(cond, msg):
    print(("  ok   " if cond else "FALLA ") + msg)
    if not cond:
        raise AssertionError(msg)


def hay(fallas, texto):
    return any(texto in f for f in fallas)


def moral_lista():
    """Un expediente de persona moral que pasa todo salvo estados de cuenta."""
    e = expediente_vacio()
    e["folio"] = "PRUEBA-01"
    e["tipo_cliente"] = "persona_moral"
    e["constitucion"].update({"inscripcion_rpc": "N-1", "fecha_inscripcion_rpc": "2020-02-20"})
    e["representante_legal"]["validado"].update({
        "nombre": "ANA PEREZ",
        "facultades": {"titulos_credito": True, "individual": True, "limite_monto": None},
        "poder": {"escritura": "1", "notario": "Lic. X", "notaria": "No. 1"},
    })
    e["grit_monedero"].update({"modelo_negocio": "prepago", "comision": "1.25%",
                               "cuota": "No aplica", "costo_tarjeta": "No aplica"})
    e["credito"]["autorizada"].update({"linea": 50000.0, "autorizada_por": "Luis Gomez"})
    e["cumplimiento"]["bc_firmado_por"] = "Marcos Siqueiros"
    e["criterio_identificacion"] = "participacion"
    return e


# ── Excepción al modelo de riesgo ────────────────────────────────────────────
base = moral_lista()
check(hay(compuertas_generacion(base), "estados de cuenta"),
      "sin excepción, una línea sin estados de cuenta no se genera")

socio = moral_lista()
socio["credito"]["excepcion_riesgo"] = {
    "motivo": "socio_comercial",
    "justificacion": "Socio comercial potencial; se omite análisis financiero.",
    "autorizada_por": "Luis Gomez", "fecha": "2026-09-28"}
check(compuertas_generacion(socio) == [],
      "una excepción completa exime de estados de cuenta y nada más: %r"
      % compuertas_generacion(socio))

sin_nombre = moral_lista()
sin_nombre["credito"]["excepcion_riesgo"] = {
    "motivo": "socio_comercial", "justificacion": "Socio comercial.",
    "autorizada_por": "  ", "fecha": "2026-09-28"}
f = compuertas_generacion(sin_nombre)
check(hay(f, "Excepción") and hay(f, "quién la autoriza"),
      "una excepción sin nombre de quien la autoriza no abre la compuerta")
check(hay(f, "estados de cuenta"),
      "una excepción incompleta no exime de estados de cuenta")

sin_justif = moral_lista()
sin_justif["credito"]["excepcion_riesgo"] = {
    "motivo": "socio_comercial", "justificacion": None,
    "autorizada_por": "Luis Gomez", "fecha": "2026-09-28"}
check(hay(compuertas_generacion(sin_justif), "justificación"),
      "una excepción sin justificación escrita no abre la compuerta")

motivo_raro = moral_lista()
motivo_raro["credito"]["excepcion_riesgo"] = {
    "motivo": "porque_si", "justificacion": "x",
    "autorizada_por": "Luis Gomez", "fecha": "2026-09-28"}
check(hay(compuertas_generacion(motivo_raro), "motivo"),
      "un motivo fuera del catálogo no abre la compuerta")

respaldo_sin_os = moral_lista()
respaldo_sin_os["credito"]["excepcion_riesgo"] = {
    "motivo": "respaldo_obligado_solidario",
    "justificacion": "El obligado solidario tiene una línea mayor autorizada.",
    "autorizada_por": "Luis Gomez", "fecha": "2026-09-28"}
check(hay(compuertas_generacion(respaldo_sin_os), "obligado solidario"),
      "el respaldo de un obligado solidario exige que haya obligado solidario")

respaldo = moral_lista()
respaldo["credito"]["excepcion_riesgo"] = dict(respaldo_sin_os["credito"]["excepcion_riesgo"])
respaldo["flags"]["obligado_solidario"] = True
respaldo["obligado_solidario"].update({"tipo": "persona_moral", "razon_social": "GARANTE SA"})
check(compuertas_generacion(respaldo) == [],
      "con obligado solidario, el respaldo exime de estados de cuenta: %r"
      % compuertas_generacion(respaldo))

sin_linea = moral_lista()
sin_linea["credito"]["excepcion_riesgo"] = dict(socio["credito"]["excepcion_riesgo"])
sin_linea["credito"]["autorizada"]["linea"] = None
check(hay(compuertas_generacion(sin_linea), "Sin línea autorizada"),
      "la excepción no sustituye a la línea autorizada")

sin_rep = moral_lista()
sin_rep["credito"]["excepcion_riesgo"] = dict(socio["credito"]["excepcion_riesgo"])
sin_rep["representante_legal"]["validado"]["facultades"]["titulos_credito"] = False
check(hay(compuertas_generacion(sin_rep), "títulos de crédito"),
      "la excepción no toca el KYC: las facultades se siguen exigiendo")

prueba = moral_lista()
prueba["credito"]["excepcion_riesgo"] = {
    "motivo": "prueba_comercial",
    "justificacion": "Cliente grande; línea de prueba de $50,000 para que empiece a usarla.",
    "autorizada_por": "Luis Gomez", "fecha": "2026-09-29"}
check(compuertas_generacion(prueba) == [],
      "una prueba comercial es motivo válido de excepción: %r"
      % compuertas_generacion(prueba))

# ── Paquete sin Grit Mobility ────────────────────────────────────────────────
con_grit = moral_lista()
check("grit_contrato" in documentos_aplicables(con_grit),
      "por default todo cliente firma Grit Mobility")

sin_grit = moral_lista()
sin_grit["sin_grit_mobility"] = {"justificacion": "Solo firma con Grit Payment.",
                                 "decidido_por": "Luis Gomez", "fecha": "2026-09-28"}
sin_grit["beneficiarios_controladores"] = [{"nombre": "X"}]
docs = documentos_aplicables(sin_grit)
check(not any(d.startswith("grit_") for d in docs),
      "sin Grit Mobility no sale ningún documento grit_: %r" % docs)
check("contrato" in docs and "pld_pm" in docs and "beneficiario_controlador" in docs,
      "sin Grit Mobility siguen saliendo contrato, PLD y BC de Grit Payment")

sin_grit["grit_monedero"]["modelo_negocio"] = None
sin_grit["constitucion"]["fecha_inscripcion_rpc"] = None
check(not hay(compuertas_generacion(sin_grit), "Grit:"),
      "sin Grit Mobility no se exigen los datos del Anexo A")

grit_incompleto = moral_lista()
grit_incompleto["sin_grit_mobility"] = {"justificacion": "Solo Grit Payment.",
                                        "decidido_por": None, "fecha": "2026-09-28"}
check("grit_contrato" in documentos_aplicables(grit_incompleto),
      "una exclusión sin nombre de quien decidió no quita los documentos")
check(hay(compuertas_generacion(grit_incompleto), "Grit Mobility"),
      "una exclusión incompleta se reporta como falla")

# ── El validador cuenta lo mismo que la compuerta ────────────────────────────
# Si la compuerta ya no exige estados de cuenta pero el validador los sigue
# pidiendo, la solicitud que ventas le reenvía al cliente pide un papel que
# nadie va a usar. Dos pantallas que se contradicen no se cree ninguna.
import validador


def pide_estados(exp):
    return any(h["asunto"] == "Faltan estados de cuenta"
               for h in validador.revisar(exp).hallazgos)


check(pide_estados(moral_lista()),
      "sin excepción, el validador pide estados de cuenta")
check(not pide_estados(socio),
      "con excepción vigente, el validador no pide estados de cuenta")
check(pide_estados(sin_nombre),
      "con excepción incompleta, el validador los sigue pidiendo")

print("\nTodas las pruebas de excepciones pasaron.")
