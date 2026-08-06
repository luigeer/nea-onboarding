# -*- coding: utf-8 -*-
"""
Pruebas del modelo de riesgo: cada una demuestra una corrección.

Se corre con:
    python tests/test_modelo_riesgo.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modelo_riesgo import evaluar, _ponderar, PESOS_MODULO

HOY = date(2026, 8, 6)

PERFIL = {"estado": "Codigo 1", "giro": "Codigo 1", "monto_solicitado": 200000.0,
          "presencia_redes": "Media", "procedencia": "Conocido Nea",
          "fecha_constitucion": date(1992, 3, 23)}

BURO_LIMPIO = {"ocurrencias_mora": 0, "saldo_vencido": 0, "saldo_actual": 0,
               "peor_edo_6m": 0, "consultas_12m": 0,
               "creditos_abiertos_ultimo_ano": 0, "creditos_abiertos": 0,
               "avales": 0, "score_pyme": 187, "prevenciones": None}

DEC_VACIA = {"ingresos_totales": 2509946.0, "utilidad_operacion": 2441072.0,
             "activo_corto_plazo": 0, "pasivo_corto_plazo": 0,
             "capital_contable": 0, "inventarios": 0, "dictaminados": "No"}

CUENTA = [[{"saldo_inicial": 100000.0, "num_depositos": 20, "monto_depositos": 500000.0,
            "num_retiros": 25, "monto_retiros": 480000.0, "saldo_final": 120000.0,
            "saldo_promedio": 400000.0, "saldo_min": 250000.0, "saldo_max": 1200000.0}]]

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def var(r, modulo, nombre):
    return r["variables"][modulo][nombre]["puntaje"]


# ── 1 y 2 · ausencia de historial ya no es peor historial ────────────────────
print("Corrección 1 y 2 · división entre cero")
v = evaluar(PERFIL, BURO_LIMPIO, DEC_VACIA, CUENTA, hoy=HOY)
l = evaluar(PERFIL, BURO_LIMPIO, DEC_VACIA, CUENTA, hoy=HOY, legado=True)
check(var(l, "buro", "porcentaje_cubierto") is None,
      "legado: sin saldo actual la variable no se podía calcular")
check(var(v, "buro", "porcentaje_cubierto") == 1.0,
      "corregido: sin deuda es 0% vencido, o sea lo mejor")
check(var(v, "buro", "porcentaje_creditos_abiertos") == 1.0,
      "corregido: sin créditos abiertos no penaliza")
check(v["modulos"]["buro"] is not None and v["modulos"]["buro"] > 0.8,
      "corregido: el módulo de buró sobrevive y sale alto")

# ── 3 · degradación elegante ─────────────────────────────────────────────────
print("Corrección 3 · degradación elegante")
sin_nada = {k: None for k in BURO_LIMPIO}
r = evaluar(PERFIL, sin_nada, DEC_VACIA, CUENTA, hoy=HOY)
check(r["modulos"]["buro"] is None, "sin ningún dato de buró, el módulo se cae")
check(r["score"] is not None, "y el score se calcula con los otros tres módulos")
check("buro" in r["modulos_sin_datos"], "queda registrado qué módulo faltó")

esperado = ((PESOS_MODULO["perfil_empresa"] * r["modulos"]["perfil_empresa"]
             + PESOS_MODULO["edos_cuenta"] * r["modulos"]["edos_cuenta"]
             + PESOS_MODULO["declaracion_anual"] * r["modulos"]["declaracion_anual"])
            / (PESOS_MODULO["perfil_empresa"] + PESOS_MODULO["edos_cuenta"]
               + PESOS_MODULO["declaracion_anual"]))
check(abs(r["score"] - esperado) < 1e-9, "los pesos se renormalizan sobre lo disponible")

# un módulo que saca exactamente 0 no debe caerse del promedio
cero = {"a": (0.5, 0.0), "b": (0.5, 0.0)}
check(_ponderar(cero, False) == 0.0,
      "un módulo que saca 0 vale 0, no 'ausente' (antes subía el score)")

# ── 4 · Peor_Edo de 0 ────────────────────────────────────────────────────────
print("Corrección 4 · peor estado de cuenta")
b0 = dict(BURO_LIMPIO, peor_edo_6m=0)
check(var(evaluar(PERFIL, b0, DEC_VACIA, CUENTA, hoy=HOY, legado=True), "buro", "peor_edo") == -2.0,
      "legado: no tener mora recibía la penalización máxima")
check(var(evaluar(PERFIL, b0, DEC_VACIA, CUENTA, hoy=HOY), "buro", "peor_edo") == 1.0,
      "corregido: no tener mora es lo mejor")
b7 = dict(BURO_LIMPIO, peor_edo_6m=7)
check(var(evaluar(PERFIL, b7, DEC_VACIA, CUENTA, hoy=HOY), "buro", "peor_edo") == -2.0,
      "corregido: un peor estado de 7 sí se sigue penalizando")

# ── 5 · ponderaciones que sumaban 1.20 ───────────────────────────────────────
print("Corrección 5 · ponderaciones del módulo de declaración anual")
dec = {"ingresos_totales": 58287737.0, "utilidad_operacion": -3117753.0,
       "activo_corto_plazo": 136812818.0, "pasivo_corto_plazo": 28466172.0,
       "capital_contable": 67011307.0, "inventarios": 0.0, "dictaminados": "No"}
vl = evaluar(PERFIL, BURO_LIMPIO, dec, CUENTA, hoy=HOY, legado=True)
vn = evaluar(PERFIL, BURO_LIMPIO, dec, CUENTA, hoy=HOY)
check(abs(vl["modulos"]["declaracion_anual"] - 0.75) < 1e-9,
      "legado: el módulo sale 0.75 sumando ponderaciones de 1.20")
check(abs(vn["modulos"]["declaracion_anual"] - 0.625) < 1e-9,
      "corregido: renormalizado sale 0.625, un 20% menos inflado")

# ── 6 · acantilado del score PYME ────────────────────────────────────────────
print("Corrección 6 · acantilado de Score_pyme_adj")
def pyme(score, legado=False):
    return var(evaluar(PERFIL, dict(BURO_LIMPIO, score_pyme=score), DEC_VACIA,
                       CUENTA, hoy=HOY, legado=legado), "buro", "score_pyme_adj")

check(pyme(190, legado=True) == -2.0 and abs(pyme(193, legado=True) - 0.31) < 1e-9,
      "legado: entre 190 y 193 de score el puntaje saltaba 2.31 puntos")
salto = abs(pyme(193) - pyme(190))
check(salto < 0.05, "corregido: el mismo tramo ahora mueve menos de 0.05")
check(abs(pyme(100) + 2.0) < 1e-9, "corregido: el extremo malo sigue valiendo −2")
check(abs(pyme(250) - 0.5) < 1e-9, "corregido: arriba del umbral no cambia nada")

# ── 7 · exclusión y comité fuera del cálculo ─────────────────────────────────
print("Corrección 7 · exclusión y comité como veto, no como número")
r = evaluar(PERFIL, dict(BURO_LIMPIO, ocurrencias_mora=5), DEC_VACIA, CUENTA, hoy=HOY)
check("exclusion" in r["vetos"] and r["veredicto"] == "Rechazado",
      "cuatro o más moras excluyen, sin importar el score")
check(isinstance(r["modulos"]["buro"], float),
      "y el módulo sigue siendo un número, no un texto")
r = evaluar(PERFIL, dict(BURO_LIMPIO, prevenciones="Amarilla"), DEC_VACIA, CUENTA, hoy=HOY)
check(r["veredicto"] == "Comité", "una prevención amarilla manda a comité")
r = evaluar(PERFIL, dict(BURO_LIMPIO, prevenciones="Roja"), DEC_VACIA, CUENTA, hoy=HOY)
check(r["veredicto"] == "Rechazado", "una prevención roja rechaza")

# ── 8 · la tercera cuenta bancaria ───────────────────────────────────────────
print("Corrección 8 · tercera cuenta bancaria")
# Dos cuentas chicas y una grande: es donde la tercera de verdad cambia el
# resultado. Con saldos que ya topan el rango máximo daría igual incluirla.
def cuenta(prom, mini, maxi):
    return [{"saldo_inicial": 10000.0, "num_depositos": 20, "monto_depositos": 100000.0,
             "num_retiros": 25, "monto_retiros": 95000.0, "saldo_final": 12000.0,
             "saldo_promedio": prom, "saldo_min": mini, "saldo_max": maxi}]

tres = [cuenta(50000.0, 20000.0, 90000.0), cuenta(50000.0, 20000.0, 90000.0),
        cuenta(500000.0, 300000.0, 1200000.0)]
vl = evaluar(PERFIL, BURO_LIMPIO, DEC_VACIA, tres, hoy=HOY, legado=True)
vn = evaluar(PERFIL, BURO_LIMPIO, DEC_VACIA, tres, hoy=HOY)
check(var(vl, "edos_cuenta", "balance_prom_entre_monto") == 0.0,
      "legado: con solo dos cuentas el saldo promedio no alcanzaba el mínimo")
check(var(vn, "edos_cuenta", "balance_prom_entre_monto") == 1.0,
      "corregido: sumando la tercera, el saldo promedio es holgado")
check(vn["modulos"]["edos_cuenta"] > vl["modulos"]["edos_cuenta"],
      "y el módulo completo mejora al dejar de ignorarla")

# ── 9 · celda vacía no es cero ───────────────────────────────────────────────
print("Corrección 9 · una celda vacía no vale cero")
sin_avales = dict(BURO_LIMPIO, avales=None)
r = evaluar(PERFIL, sin_avales, DEC_VACIA, CUENTA, hoy=HOY)
check(var(r, "buro", "no_avales") is None,
      "sin dato de avales la variable no inventa un cero")
con_cero = evaluar(PERFIL, dict(BURO_LIMPIO, avales=0), DEC_VACIA, CUENTA, hoy=HOY)
check(var(con_cero, "buro", "no_avales") == 1.0,
      "pero cero avales de verdad sí puntúa como lo mejor")
check(r["modulos"]["buro"] != con_cero["modulos"]["buro"],
      "y los dos casos dan resultados distintos, que es el punto")

# ── el modelo sigue siendo el mismo donde no había defecto ───────────────────
print("Regresión · lo que no se tocó no cambió")
for campo, valor in [("estado", "Codigo 2"), ("giro", "Codigo 3"),
                     ("presencia_redes", "Baja"), ("procedencia", "Marketing")]:
    p = dict(PERFIL, **{campo: valor})
    a = evaluar(p, BURO_LIMPIO, DEC_VACIA, CUENTA, hoy=HOY, legado=True)
    b = evaluar(p, BURO_LIMPIO, DEC_VACIA, CUENTA, hoy=HOY)
    check(a["modulos"]["perfil_empresa"] == b["modulos"]["perfil_empresa"],
          "perfil de empresa con %s=%s no cambia" % (campo, valor))

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
