# -*- coding: utf-8 -*-
"""Pedir extracciones nuevas a Syntage, solo de las fuentes sin costo.

Buró de Crédito, BIL y Verificación de Sociedad se cobran aparte. Un barrido
que actualiza a cien clientes no puede, ni por descuido, pedir una de esas: por
eso la lista de extractores es cerrada y la función que llama a la API se niega
a mandar cualquier otro, antes de tocar la red.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import syntage as s


def check(cond, msg):
    print(("  ok   " if cond else "FALLA ") + msg)
    if not cond:
        raise AssertionError(msg)


HOY = date(2026, 9, 30)

# ── Qué se pide ──────────────────────────────────────────────────────────────
cuerpos = s.cuerpos_extraccion("abc-123", hoy=HOY)
extractores = [c["extractor"] for c in cuerpos]
check(all(c["entity"] == "/entities/abc-123" for c in cuerpos), "cada petición apunta a la entidad")
check(set(extractores) == set(s.EXTRACTORES_SIN_COSTO),
      "se piden todos los extractores sin costo: %r" % sorted(set(extractores)))
check(not set(extractores) & set(s.EXTRACTORES_CON_COSTO),
      "ninguno de los que cuestan (Buró, BIL, Verificación de Sociedad)")
check(extractores.count("invoice") == 2, "facturas emitidas y recibidas van por separado")
inv = [c["options"] for c in cuerpos if c["extractor"] == "invoice"]
check({o["issued"] for o in inv} == {True, False}, "una de emitidas y otra de recibidas")
periodo = next(c for c in cuerpos if c["extractor"] == "annual_tax_return")["options"]["period"]
check(periodo["from"] == "2023-01-01" and periodo["to"] == "2026-09-30",
      "el periodo es de 3 años desde el 1 de enero, como el onboarding: %r" % periodo)

# ── La barrera ───────────────────────────────────────────────────────────────
llamadas = []


def pedir_falso(ruta, metodo="GET", cuerpo=None, **kw):
    llamadas.append((metodo, ruta, cuerpo))
    return {"id": "ext-1", "status": "pending"}


for caro in s.EXTRACTORES_CON_COSTO:
    try:
        s.pedir_extraccion({"entity": "/entities/x", "extractor": caro}, pedir=pedir_falso)
        check(False, "%s debió rechazarse" % caro)
    except ValueError:
        pass
check(llamadas == [], "un extractor con costo se rechaza sin llamar a la API")

r = s.pedir_extraccion(cuerpos[0], pedir=pedir_falso)
check(r["resultado"] == "pedida" and llamadas[-1][0] == "POST" and llamadas[-1][1] == "/extractions",
      "un extractor sin costo se manda con POST /extractions")


def pedir_409(ruta, metodo="GET", cuerpo=None, **kw):
    raise s.ErrorSyntage(409, "already running", ruta)


check(s.pedir_extraccion(cuerpos[0], pedir=pedir_409)["resultado"] == "en_curso",
      "un 409 (ya hay una igual corriendo) no es error: queda como en curso")

# ── A quién se actualiza ─────────────────────────────────────────────────────
filas = [{"rfc": "VIEJO", "ult_extr": "2023-03-08", "corriendo": 0},
         {"rfc": "RECIENTE", "ult_extr": "2026-09-20", "corriendo": 0},
         {"rfc": "CORRIENDO", "ult_extr": "2023-01-01", "corriendo": 2},
         {"rfc": "NUNCA", "ult_extr": "", "corriendo": 0}]
sel = [f["rfc"] for f in s.seleccion_para_actualizar(filas, dias_minimos=365, hoy=HOY)]
check(sel == ["NUNCA", "VIEJO"],
      "se eligen los más viejos primero, y no los que ya tienen algo corriendo: %r" % sel)

print("\nTodas las pruebas de actualización de Syntage pasaron.")
