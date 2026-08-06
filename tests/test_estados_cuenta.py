# -*- coding: utf-8 -*-
"""
Pruebas del puente entre el Bank Statement Analyzer y el modelo de riesgo.

Se corre con:
    python tests/test_estados_cuenta.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from estados_cuenta import desde_analizador, resumen, DatosInsuficientes

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def ficha(cuenta="1234", moneda="MXN", fin="2026-06-30", prom=100000, **extra):
    d = {"banco": "BBVA", "cuenta_bancaria": cuenta, "moneda": moneda,
         "fecha_inicial": fin[:8] + "01", "fecha_final": fin,
         "saldo_inicial": "50,000.00", "numero_depositos": 12,
         "monto_depositos": "$500,000.00", "numero_retiros": 30,
         "monto_retiros": "480,000.00", "saldo_final": 70000,
         "saldo_promedio": prom, "saldo_minimo": 20000, "saldo_maximo": 300000}
    d.update(extra)
    return {"Informacion Bancaria": d}


# ── formato del analizador ───────────────────────────────────────────────────
print("Lectura del formato del analizador")
c, avisos = desde_analizador([ficha()])
p = c[0][0]
check(p["saldo_inicial"] == 50000.0, "limpia el formato de moneda con comas")
check(p["monto_depositos"] == 500000.0, "y con signo de pesos")
check(p["num_depositos"] == 12 and p["num_retiros"] == 30, "renombra los conteos")
check(p["saldo_min"] == 20000 and p["saldo_max"] == 300000, "renombra mínimo y máximo")

# ── orden de los periodos ────────────────────────────────────────────────────
print("Orden de los periodos")
c, _ = desde_analizador([ficha(fin="2026-04-30", prom=10),
                         ficha(fin="2026-06-30", prom=30),
                         ficha(fin="2026-05-31", prom=20)])
check([x["saldo_promedio"] for x in c[0]] == [30, 20, 10],
      "el más reciente queda primero aunque lleguen desordenados")
c, _ = desde_analizador([ficha(fin="30/04/2026", prom=10), ficha(fin="30/06/2026", prom=30)])
check([x["saldo_promedio"] for x in c[0]] == [30, 10], "también con fechas dd/mm/aaaa")

# ── varias cuentas ───────────────────────────────────────────────────────────
print("Separación por cuenta")
c, _ = desde_analizador([ficha(cuenta="1111"), ficha(cuenta="2222"),
                         ficha(cuenta="1111", fin="2026-05-31")])
check(len(c) == 2, "dos cuentas distintas producen dos grupos")
check(sorted(len(x) for x in c) == [1, 2], "y cada una conserva sus periodos")

# ── moneda ───────────────────────────────────────────────────────────────────
print("Moneda")
try:
    desde_analizador([ficha(moneda="USD")])
    check(False, "una cuenta en dólares sin tipo de cambio debe detenerse")
except DatosInsuficientes:
    check(True, "una cuenta en dólares sin tipo de cambio debe detenerse")

c, avisos = desde_analizador([ficha(moneda="USD", prom=30000)], tipo_cambio={"USD": 18.4})
check(c[0][0]["saldo_promedio"] == 30000 * 18.4, "con tipo de cambio, convierte los saldos")
check(c[0][0]["num_depositos"] == 12, "pero no toca los conteos, que no son dinero")
check(any("USD" in a for a in avisos), "y deja constancia de la conversión")

c, _ = desde_analizador([ficha(cuenta="1111", prom=50000),
                         ficha(cuenta="2222", moneda="USD", prom=30000)],
                        tipo_cambio={"USD": 18.4})
total = sum(x[0]["saldo_promedio"] for x in c)
check(abs(total - (50000 + 552000)) < 1e-6,
      "mezclar pesos y dólares ya no subestima al cliente")

# ── cifras reconciliadas ─────────────────────────────────────────────────────
print("Flujo operativo contra cifras de encabezado")
c, avisos = desde_analizador([ficha()])
check(any("encabezado" in a for a in avisos),
      "sin cifras reconciliadas, avisa que las de encabezado están infladas")

c, avisos = desde_analizador([ficha(numero_depositos_operativo=4,
                                    numero_retiros_operativo=6,
                                    monto_depositos_operativo=120000)])
check(c[0][0]["num_depositos"] == 4 and c[0][0]["num_retiros"] == 6,
      "con cifras reconciliadas, esas mandan sobre las de encabezado")
check(c[0][0]["monto_depositos"] == 120000, "el monto reconciliado también")
check(not any("encabezado" in a for a in avisos), "y ya no avisa")
check(resumen(c)[0]["reconciliado"] is True, "el resumen lo refleja")

c, _ = desde_analizador([ficha(numero_depositos_operativo=4)], usar_operativo=False)
check(c[0][0]["num_depositos"] == 12, "se puede pedir explícitamente el encabezado")

# ── el efecto real sobre el modelo ───────────────────────────────────────────
print("Efecto sobre el modelo de riesgo")
from datetime import date
from modelo_riesgo import evaluar
P = {"estado": "Codigo 1", "giro": "Codigo 1", "monto_solicitado": 200000.0,
     "presencia_redes": "Media", "procedencia": "Conocido Nea",
     "fecha_constitucion": date(1992, 3, 23)}
B = {k: 0 for k in ("ocurrencias_mora", "saldo_vencido", "saldo_actual", "peor_edo_6m",
                    "consultas_12m", "creditos_abiertos_ultimo_ano", "creditos_abiertos",
                    "avales")}
B.update(score_pyme=250, prevenciones=None)
D = {k: None for k in ("ingresos_totales", "utilidad_operacion", "activo_corto_plazo",
                       "pasivo_corto_plazo", "capital_contable", "inventarios",
                       "dictaminados")}

# Overnight: 45 movimientos de encabezado contra 9 operativos reales
inflado, _ = desde_analizador([ficha(numero_depositos=45, numero_retiros=45)])
real, _ = desde_analizador([ficha(numero_depositos=45, numero_retiros=45,
                                  numero_depositos_operativo=4,
                                  numero_retiros_operativo=5)])
a = evaluar(P, B, D, inflado, hoy=date(2026, 8, 6))
b = evaluar(P, B, D, real, hoy=date(2026, 8, 6))
check(a["variables"]["edos_cuenta"]["no_prom_movimientos"]["puntaje"] == 1.0,
      "con cifras de encabezado, los ciclos overnight dan el puntaje máximo")
check(b["variables"]["edos_cuenta"]["no_prom_movimientos"]["puntaje"] == 0.3,
      "con el flujo operativo real, el puntaje cae al mínimo")
check(a["modulos"]["edos_cuenta"] > b["modulos"]["edos_cuenta"],
      "o sea que el encabezado premiaba mover dinero entre cuentas propias")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
