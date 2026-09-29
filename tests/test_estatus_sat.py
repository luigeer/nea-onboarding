# -*- coding: utf-8 -*-
"""Qué estatus del padrón del SAT permite abrir un expediente.

"REACTIVADO" es un contribuyente que estuvo suspendido y volvió a operar: para
el SAT está vivo, igual que "ACTIVO". Tratarlo como suspendido detenía a
clientes reales —Corporación Interamericana de Logística lleva así desde 2005—.
Lo que sigue sin aceptarse es todo lo demás: suspendido, cancelado, etcétera.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date

from schema_expediente import estatus_sat_aceptable, expediente_vacio
import validador


def check(cond, msg):
    print(("  ok   " if cond else "FALLA ") + msg)
    if not cond:
        raise AssertionError(msg)


check(estatus_sat_aceptable("ACTIVO"), "ACTIVO se acepta")
check(estatus_sat_aceptable("REACTIVADO"), "REACTIVADO se acepta")
check(estatus_sat_aceptable(" reactivado "), "sin importar mayúsculas ni espacios")
check(not estatus_sat_aceptable("SUSPENDIDO"), "SUSPENDIDO no se acepta")
check(not estatus_sat_aceptable("CANCELADO"), "CANCELADO no se acepta")


def alta_por_estatus(estatus):
    e = expediente_vacio()
    e["tipo_cliente"] = "persona_moral"
    e["cliente"]["validado"]["situacion_contribuyente"] = estatus
    r = validador.revisar(e, hoy=date(2026, 9, 29))
    return any("no está ACTIVO" in h["asunto"] for h in r.hallazgos)


check(not alta_por_estatus("REACTIVADO"), "el validador no frena a un REACTIVADO")
check(alta_por_estatus("SUSPENDIDO"), "el validador sí frena a un SUSPENDIDO")

print("\nTodas las pruebas de estatus SAT pasaron.")
