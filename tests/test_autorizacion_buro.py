# -*- coding: utf-8 -*-
"""La autorización de consulta de buró viaja dentro del paquete de firma.

Cuando no hace falta consultar buró antes de autorizar —la línea no pasa por el
modelo—, la autorización se firma junto con los contratos en vez de pedirse
antes. Eso sale con `flags.buro_en_paquete`: el documento se agrega al paquete,
y el validador deja de pedirlo como faltante, porque ya no le toca al cliente
mandarlo aparte.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date

import pdfplumber

from adaptadores import ADAPTADORES
from schema_expediente import documentos_aplicables, expediente_vacio
from generar_paquete import CATALOGO, _firmantes
import firma
import validador
import verificador


def check(cond, msg):
    print(("  ok   " if cond else "FALLA ") + msg)
    if not cond:
        raise AssertionError(msg)


def moral():
    e = expediente_vacio()
    e["folio"] = "PRUEBA-01"
    e["tipo_cliente"] = "persona_moral"
    e["fechas"]["operacion"] = "2026-09-29"
    v = e["cliente"]["validado"]
    v.update({"razon_social": "EMPRESA EJEMPLO, S.A. DE C.V.", "rfc": "EEJ010101AB1",
              "telefono": "55 1234 5678"})
    v["domicilio"].update({"calle": "LIBRAMIENTO LA JOYA", "num_ext": "3 INT. B",
                           "colonia": "SANTA ANA TLALTEPAN", "cp": "54870",
                           "municipio": "CUAUTITLAN", "estado": "MEXICO"})
    e["representante_legal"]["validado"]["nombre"] = "Ana Pérez López"
    e["representante_legal"]["propuesto"]["correo"] = "ana@ejemplo.com"
    return e


# ── Cuándo se incluye ────────────────────────────────────────────────────────
e = moral()
check("autorizacion_buro" not in documentos_aplicables(e),
      "sin la marca, la autorización de buró no va en el paquete")
e["flags"]["buro_en_paquete"] = True
check("autorizacion_buro" in documentos_aplicables(e),
      "con la marca, la autorización de buró va en el paquete")


def pide_buro(exp):
    return any("buró" in h["asunto"] and h["asunto"].startswith("Falta")
               for h in validador.revisar(exp, hoy=date(2026, 9, 29)).hallazgos)


check(pide_buro(moral()), "sin la marca, el validador pide la autorización de buró")
check(not pide_buro(e), "con la marca, el validador ya no la pide al cliente")

# ── Qué dice ─────────────────────────────────────────────────────────────────
d = ADAPTADORES["autorizacion_buro"](e)
check(d["tipo_persona"] == "pm", "persona moral marca la casilla PM")
check(d["solicitante"] == "EMPRESA EJEMPLO, S.A. DE C.V.", "el solicitante es la razón social")
check(d["rep_legal"] == "ANA PÉREZ LÓPEZ", "el representante legal va en su renglón")
check(d["rfc"] == "EEJ010101AB1", "en persona moral va el RFC de la empresa")
check(d["municipio"] == "CUAUTITLAN" and d["cp"] == "54870", "domicilio de la empresa")
check(d["correo"] == "ana@ejemplo.com", "el correo del representante")
check(d["fecha"] == "29 de septiembre de 2026", "la fecha de firma es la de operación")

pf = moral()
pf["tipo_cliente"] = "pfae"
pf["representante_legal"]["validado"]["rfc"] = "PELA800101XX1"
dpf = ADAPTADORES["autorizacion_buro"](pf)
check(dpf["tipo_persona"] == "pfae" and dpf["rep_legal"] == "",
      "PFAE marca su casilla y no lleva representante legal")

# ── El PDF ───────────────────────────────────────────────────────────────────
sufijo, fn, template, etiqueta = CATALOGO["autorizacion_buro"]
ruta = os.path.join(tempfile.mkdtemp(), "buro.pdf")
fn(d, ruta, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", template)) if template else fn(d, ruta)
with pdfplumber.open(ruta) as pdf:
    texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
for esperado in ("GRIT PAYMENT SOLUTIONS", "EMPRESA EJEMPLO, S.A. DE C.V.",
                 "EEJ010101AB1", "ANA PÉREZ LÓPEZ", "29 de septiembre de 2026",
                 "3 años", "artículo 28"):
    check(esperado in texto, "el PDF dice %r" % esperado)
check(verificador.verificar_documento("autorizacion_buro", ruta, e) == [],
      "el verificador no encuentra hallazgos en la autorización")

# ── Quién firma y dónde ─────────────────────────────────────────────────────
f = _firmantes("autorizacion_buro", e)
check([x["rol"] for x in f] == ["cliente"], "solo firma el cliente")
check("autorizacion_buro" in firma.ORDEN and "autorizacion_buro" in firma.ETIQUETAS,
      "tiene lugar y nombre en el plan de firma")

print("\nTodas las pruebas de la autorización de buró pasaron.")
