# -*- coding: utf-8 -*-
"""
Pruebas del detalle SPEI de BBVA (bbva.detalle_spei), para comprobar en Banxico.

Solo T17 (SPEI ENVIADO) y T20 (SPEI RECIBIDO) traen el bloque de cuatro
renglones con la clave de rastreo; T09 (TEF RECIBIDO) es un sistema distinto y
no la trae, así que no genera CEP y no debe aparecer aquí.

El caso que más importa: un renglón que no tiene la forma de cuenta o de clave
de rastreo no se adivina. Ya pasó con `ceps.py` que una etiqueta se leyó donde
no iba y el beneficiario salió mal; aquí el riesgo es peor porque no hay
etiqueta que avise el error, solo posición. Por eso un candidato dudoso se
devuelve con `revisar_manual=True` en vez de una clave inventada.

Todos los datos son inventados.

Se corre con:
    python tests/test_bbva_spei.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bbva

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── LO IMPORTANTE · un bloque normal se lee completo ─────────────────────────
print("Bloque SPEI normal, sin sobresaltos")
renglones = [
    "01/JUL 01/JUL T20 SPEI RECIBIDOBAJIO 4,000.00",
    "4232535traspaso Ref. 0183820388 030",
    "00030470900027271570",
    "BB4232535018384",
    "RC INTERCOMERCE SA DE CV",
]
movs = bbva._bloques_spei(renglones, 2026)
check(len(movs) == 1, "un bloque produce un movimiento")
m = movs[0]
check(m["fecha"] == "2026-07-01", "la fecha se arma con el anio dado")
check(m["tipo"] == "spei_recibido", "T20 es recibido")
check(m["banco_contraparte"] == "BAJIO", "el banco declarado sale del encabezado, tal cual")
check(m["monto"] == 4000.0, "el monto es el primero de la linea")
check(m["referencia"] == "0183820388", "la referencia sale del renglon Ref.")
check(m["clave_rastreo"] == "BB4232535018384", "la clave de rastreo es el tercer renglon del bloque")
check(m["contraparte"] == "RC INTERCOMERCE SA DE CV", "el nombre es el cuarto renglon")
check(m["revisar_manual"] is False, "un bloque completo y valido no se manda a revisar")

# ── LO IMPORTANTE · SPEI ENVIADO trae al beneficiario, no al propio titular ──
print()
print("SPEI enviado")
renglones = [
    "07/JUL 07/JUL T17 SPEI ENVIADO BAJIO 5,000.00",
    "0070726F4721 Ref. 0026195715 030",
    "00030470706483502016",
    "BNET01002607070026195715",
    "ISMAEL DAVID HERRERA",
]
m = bbva._bloques_spei(renglones, 2026)[0]
check(m["tipo"] == "spei_enviado", "T17 es enviado")
check(m["contraparte"] == "ISMAEL DAVID HERRERA",
      "en un enviado el nombre del bloque es el beneficiario, no RC Intercomerce")

# ── LO IMPORTANTE · TEF no es SPEI y no genera CEP ───────────────────────────
print()
print("TEF recibido (T09): no es SPEI, no trae clave de rastreo, no se incluye")
renglones = [
    "10/JUL 10/JUL T09 TEF RECIBIDO HSBC 290,000.00",
    "0000001100200030999226 Ref. 3556095933 021",
    "10/JUL 10/JUL I72 VENTAS TDC INTER 1,855.92",
    "144725266 Ref. 144725266",
]
movs = bbva._bloques_spei(renglones, 2026)
check(movs == [], "T09 (TEF) no aparece: solo SPEI tiene CEP")

# ── LO IMPORTANTE · un salto de pagina no debe partir el bloque ──────────────
print()
print("El bloque partido por un salto de pagina se recompone")
renglones = [
    "21/JUL 21/JUL T20 SPEI RECIBIDOBAJIO 22,000.00",
    "2359049traspaso Ref. 0106404587 030",
    "BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE, GRUPO FINANCIERO BBVA MEXICO",
    "Av. Paseo de la Reforma 510, Col. Juarez, Alcaldia Cuauhtemoc, C.P. 06600, Ciudad de Mexico. Mexico R.F.C. BBA830831LJ2",
    "Estado de Cuenta",
    "MAESTRA PYME BBVA",
    "PAGINA 9 / 21",
    "No. Cuenta 0167243499",
    "No. Cliente 67612896",
    "FECHA SALDO",
    "OPER LIQ COD. DESCRIPCION REFERENCIA CARGOS ABONOS OPERACION LIQUIDACION",
    "00030470900022222222",
    "BB2359049020799",
    "RC INTERCOMERCE SA DE CV",
]
m = bbva._bloques_spei(renglones, 2026)[0]
check(m["clave_rastreo"] == "BB2359049020799",
      "el boilerplate de pie y encabezado se filtra antes de leer el detalle")
check(m["revisar_manual"] is False, "recompuesto, el bloque vuelve a ser valido")

# ── LO IMPORTANTE · lo que no tiene forma de cuenta/clave no se inventa ──────
print()
print("Un bloque con forma rara se manda a revisar, no se adivina")
renglones = [
    "14/JUL 14/JUL T20 SPEI RECIBIDOSCOTIABANK 647,553.44",
    "9000533 COMPRA VENTA DE DOCUMENTOS EL Ref. 0160864093",
    "AVISO DE COBRO EN LINEA",
    "Ver detalle en banca en linea",
]
m = bbva._bloques_spei(renglones, 2026)[0]
check(m["revisar_manual"] is True,
      "ni la forma de cuenta ni la de 'banco a tercero' aplican: no se lee como si aplicara")
check(m["clave_rastreo"] is None, "sin candidato valido, la clave queda en None, no en un dato equivocado")
check(m["monto"] == 647553.44, "lo que si es confiable -fecha, monto, banco declarado- se conserva")

# ── LO IMPORTANTE · "banco a tercero" es una forma valida, no un error ───────
print()
print("Pago a tercero sin cuenta beneficiaria propia (patron de Scotiabank)")
renglones = [
    "14/JUL 14/JUL T20 SPEI RECIBIDOSCOTIABANK 647,553.44",
    "9000533 COMPRA VENTA DE DOCUMENTOS EL Ref. 0160864093",
    "044",
    "BANCO A TERCERO",
    "2026071440044B35W0000000091218",
    "SCOTIABANK",
]
m = bbva._bloques_spei(renglones, 2026)[0]
check(m["revisar_manual"] is False,
      "'BANCO A TERCERO' es una forma reconocida, no una que se descarta")
check(m["clave_rastreo"] == "2026071440044B35W0000000091218",
      "aqui la clave de rastreo cae un renglon mas adelante que en el bloque normal")
check(m["cuenta_contraparte"] is None,
      "no hay CLABE propia del beneficiario: el pago va a el banco, no a una cuenta")
check(m["contraparte"] == "SCOTIABANK", "el nombre es el ultimo renglon del bloque")

# Un bloque que se corta porque el estado de cuenta termina ahi (no hay
# renglones de detalle, ya sea por corte de pagina o fin del documento).
renglones = ["31/JUL 31/JUL T20 SPEI RECIBIDOSANTANDER 11,800.00"]
m = bbva._bloques_spei(renglones, 2026)[0]
check(m["revisar_manual"] is True, "sin ningun renglon de detalle, tampoco se inventa nada")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
