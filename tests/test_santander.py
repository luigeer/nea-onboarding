# -*- coding: utf-8 -*-
"""
Pruebas del lector de estados de cuenta de Santander (Cuenta Santander PyME).

Como en test_mifel.py, la extracción del PDF se comprueba contra el propio
estado de cuenta: Santander imprime el saldo después de cada movimiento y el
total de depósitos y de retiros, así que `cuadra` decide si un estado mal leído
se guarda o no.

Lo que además se prueba aquí es el detalle de los SPEI. Santander escribe debajo
de cada transferencia a qué banco se envió o de cuál se recibió, y su clave de
rastreo. Con eso se consulta el CEP en Banxico, que es lo que convierte un
estado de cuenta —un PDF que cualquiera puede editar— en evidencia.

Todos los datos son inventados.

Se corre con:
    python tests/test_santander.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bancos
import ceps
import santander

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


CLABE_PROPIA = "014000000000000001"

RENGLONES = [
    "FECHA FOLIO DESCRIPCION DEPOSITO RETIRO SALDO",
    "01-JUN-2026 0000000DEPOSITO VENTAS DEL DIA AFIL.-000000001 1,000.00 11,000.00",
    "03-JUN-2026 9110137PAGO TRANSFERENCIA SPEI HORA 09:11:07 4,000.00 7,000.00",
    "ENVIADO A BBVA MEXICO",
    "A LA CUENTA 012000000000000002",
    "AL CLIENTE EMPRESA EJEMPLO SADECV (1)",
    "(1) DATO NO VERIFICADO POR ESTA INSTITUCION",
    "CLAVE DE RASTREO 20260603400140BET0000000000001",
    "REF 9110137",
    "CONCEPTO Pago a proveedor",
    "08-JUN-2026 0817958ABONO TRANSFERENCIA SPEI HORA 12:56:02 300.00 7,300.00",
    "RECIBIDO DE BANREGIO",
    "CLAVE DE RASTREO 058-22/06/2026/22-210YMJA919",
    "09-JUN-2026 0000000COBRO IVA AFIL.-000000001 16.00 7,284.00",
]


# ── Detalle de los SPEI ──────────────────────────────────────────────────────
print("SPEI con su clave de rastreo, listos para el CEP")
spei = santander.spei(RENGLONES, CLABE_PROPIA)
check(len(spei) == 2, "solo los SPEI, no las ventas ni las comisiones (%d)" % len(spei))

env = spei[0] if spei else {}
check(env.get("tipo") == "spei_enviado", "un PAGO TRANSFERENCIA SPEI es un envío")
check(env.get("fecha") == "2026-06-03", "la fecha sale en AAAA-MM-DD (%r)" % env.get("fecha"))
check(env.get("monto") == 4000.0, "el monto es el del movimiento, no el saldo (%r)" % env.get("monto"))
check(env.get("clave_rastreo") == "20260603400140BET0000000000001", "trae su clave de rastreo")
check(env.get("banco_emisor") == "Santander", "lo emite Santander")
check(env.get("institucion_receptora") == "BBVA MEXICO", "lo recibe el banco de 'ENVIADO A'")
check(env.get("cuenta_beneficiaria") == "012000000000000002", "la cuenta de 'A LA CUENTA'")
check(env.get("beneficiario") == "EMPRESA EJEMPLO SADECV",
      "el beneficiario, sin la nota de dato no verificado (%r)" % env.get("beneficiario"))

rec = spei[1] if len(spei) > 1 else {}
check(rec.get("tipo") == "spei_recibido", "un ABONO TRANSFERENCIA SPEI es un depósito")
check(rec.get("institucion_ordenante") == "BANREGIO", "lo envía el banco de 'RECIBIDO DE'")
check(rec.get("banco_emisor") == "BANREGIO", "en el CEP el emisor es el banco que envió")
check(rec.get("cuenta_beneficiaria") == CLABE_PROPIA, "la cuenta beneficiaria es la propia")
check(rec.get("clave_rastreo") == "058-22/06/2026/22-210YMJA919",
      "una clave con guiones y diagonales se conserva completa")

# En algunos meses Santander pega el año con el folio, sin espacio:
# "03-AGO-20264680363ABONO ...". Exigir el espacio dejaba un mes entero sin SPEI.
pegado = santander.spei([
    "03-AGO-20264680363ABONO TRANSFERENCIA SPEI HORA 11:40:55 1,944.97 44,642.32",
    "RECIBIDO DE Mercado Pago W",
    "CLAVE DE RASTREO CPO170974799387"], CLABE_PROPIA)
check(len(pegado) == 1 and pegado[0]["fecha"] == "2026-08-03"
      and pegado[0]["monto"] == 1944.97 and pegado[0]["clave_rastreo"] == "CPO170974799387",
      "un renglón con el año pegado al folio también se lee (%r)" % pegado)

# ── Lo que pide el formulario de Banxico ─────────────────────────────────────
print("Instrucciones para el formulario de Banxico")
i_env = ceps.instrucciones(env)
check(i_env["banco_emisor"] == "Santander" and i_env["banco_receptor"] == "BBVA MEXICO",
      "un envío de Santander se consulta con emisor Santander (%r)" % i_env["banco_emisor"])
i_rec = ceps.instrucciones(rec)
check(i_rec["banco_emisor"] == "BANREGIO" and i_rec["banco_receptor"] == "Santander",
      "un depósito se consulta con el emisor que envió y receptor Santander (%r → %r)"
      % (i_rec["banco_emisor"], i_rec["banco_receptor"]))
bajio = ceps.instrucciones({"fecha": "2026-06-01", "clave_rastreo": "X",
                            "institucion_receptora": "BBVA", "monto": 1.0})
check(bajio["banco_emisor"] == "BanBajío",
      "un movimiento de Banco del Bajío sigue consultándose como antes")

# ── Cuadre ───────────────────────────────────────────────────────────────────
print("Cuadre contra el saldo corrido que declara Santander")


def mov(tipo, monto, saldo):
    return {"fecha": "2026-06-01", "descripcion": "x", "tipo": tipo,
            "monto": monto, "saldo": saldo}


enc = {"saldo_inicial": 1000.0, "saldo_final": 1300.0,
       "monto_depositos": 500.0, "monto_retiros": 200.0}
ok, _ = santander.cuadra(enc, [mov("abono", 500.0, 1500.0), mov("cargo", 200.0, 1300.0)])
check(ok, "cuando la cadena de saldos y los totales coinciden, cuadra")
ok, _ = santander.cuadra(dict(enc, saldo_final=700.0),
                         [mov("cargo", 500.0, 500.0), mov("abono", 200.0, 700.0)])
check(not ok, "un movimiento leído en la columna equivocada rompe la cadena")

# ── Registro ─────────────────────────────────────────────────────────────────
check(bancos.PARSERS.get("santander") is santander,
      "Santander está registrado en bancos.PARSERS")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
