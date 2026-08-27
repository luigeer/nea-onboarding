# -*- coding: utf-8 -*-
"""
Pruebas de comisiones_monedero.py.

Las facturas de prueba son inventadas, pero las DESCRIPCIONES son las reales:
se copiaron del barrido de las 909 facturas que Pluxee le emitió a un cliente
real, más las de Toka, Efectivale y Si Vale. Ahí está el valor de este
archivo — la clasificación de esos textos es toda la regla de negocio.

Se corre con:
    python tests/test_comisiones_monedero.py
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comisiones_monedero as cm

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ─────────────────────────────────────────────────────────────────────────────
# clasificar(): los textos reales con los que facturan los monederos
# ─────────────────────────────────────────────────────────────────────────────
# Comisión dicha con su nombre.
for d in ("Comisión", "COMISION", "CARGO DE COMISION", "Cargo de Comisión"):
    check(cm.clasificar(d) == "explicita",
          "%r es comisión explícita: %r" % (d, cm.clasificar(d)))

# Comisión con otro nombre: se cobra por mover el dinero, no por un servicio
# aparte. En el cliente más grande es el renglón MAYOR ($1,812 en promedio,
# 285 veces) — dejarlo fuera subestima 3.17 puntos porcentuales de 4.37.
for d in ("SERVICIO ADMINISTRATIVO", "Cargo Administrativo", "CARGO ADMINISTRATIVO",
          "CARGO POR DISPERSION", "CARGO DE DISPERSION"):
    check(cm.clasificar(d) == "administrativa",
          "%r es comisión administrativa: %r" % (d, cm.clasificar(d)))

# ── FONDEO: el dinero, no una cuota ───────────────────────────────────────
# La distinción más importante de este módulo. Estos conceptos son el saldo
# que se carga a las tarjetas: en un cliente real suman $4.5 MILLONES contra
# $68 mil de comisión. Contarlos como cargo daba comisiones de 3,090%.
for d in ("MAS DESPENSA CARGA DE SALDOS", "FAM RESTAURANTE CARGA DE SALDOS",
          "GASOLINA MAGNA FLEET CARGA DE SALDOS", "DESPENSA CARGA DE SALDOS",
          "GASOLINA MAGNA FLEET HABILITACION DE RECURSOS", "DISPERSION",
          "Dispersión", "CONSUMOS DE COMBUSTIBLE DE MONEDEROS ELECTRONICOS"):
    check(cm.clasificar(d) == "fondeo",
          "%r es fondeo (el dinero), no un cargo: %r" % (d, cm.clasificar(d)))

# El filo del cuchillo: "DISPERSION" a secas es el dinero ($2,197,500 en un
# cliente real); "CARGO POR DISPERSION" es la cuota por dispersarlo ($254 en
# promedio). Una palabra de diferencia, tres órdenes de magnitud.
check(cm.clasificar("DISPERSION") == "fondeo"
      and cm.clasificar("CARGO POR DISPERSION") == "administrativa",
      "'DISPERSION' es el dinero y 'CARGO POR DISPERSION' la cuota: %r vs %r"
      % (cm.clasificar("DISPERSION"), cm.clasificar("CARGO POR DISPERSION")))

# Servicios que sí son aparte: tarjetas, envíos, anualidad.
for d in ("CARGO POR EMISION DE PLÁSTICO", "ENVIO", "SERVICIO DE ENTREGA",
          "EMISION DE TARJETA", "REPOSICION DE TARJETA", "ANUALIDAD",
          "ANUALIDAD POR CLIENTE", "CARGO POR REPOSICION DE PLÁSTICO",
          "Emisión Tarjeta Reposición", "MAS DESPENSA TARJETAS REPOSICIONES",
          "PLASTICOS", "Reposicion tarjetas titulares", "Otros"):
    check(cm.clasificar(d) == "otros",
          "%r es otro cargo, no comisión: %r" % (d, cm.clasificar(d)))

# La trampa: este texto CONTIENE la palabra comisión y dice justo lo
# contrario. Aparece 172 veces en el cliente más grande, con $1.00 cada vez.
# Un buscador por subcadena lo cobraría como comisión.
check(cm.clasificar("NO EXISTE COMISION POR RAZONES COMERCIALES") == "declara_cero",
      "'NO EXISTE COMISION...' declara que NO hay comisión: %r"
      % cm.clasificar("NO EXISTE COMISION POR RAZONES COMERCIALES"))
check(cm.clasificar("no existe comisión por razones comerciales") == "declara_cero",
      "y también en minúsculas y con acento")

check(cm.clasificar("") == "otros", "una descripción vacía no truena")
check(cm.clasificar(None) == "otros", "un None tampoco")


# ── es_combustible(): qué parte del fondeo es gasolina ────────────────────
# Un cliente puede mover $4.5M por su monedero y que solo $73 mil sea
# gasolina: el resto es despensa y restaurante. Sin separar eso, su comisión
# se le atribuye al combustible cuando en realidad es de otro producto.
for d in ("GASOLINA MAGNA FLEET CARGA DE SALDOS", "DIESEL FLEET CARGA DE SALDOS",
          "CONSUMOS DE COMBUSTIBLE DE MONEDEROS ELECTRONICOS",
          "GASOLINA PREMIUM CARGA DE SALDOS"):
    check(cm.es_combustible(d), "%r es fondeo de combustible" % d)
for d in ("MAS DESPENSA CARGA DE SALDOS", "FAM RESTAURANTE CARGA DE SALDOS",
          "DESPENSA CARGA DE SALDOS", "DISPERSION"):
    check(not cm.es_combustible(d),
          "%r NO se puede dar por combustible: 'DISPERSION' a secas no dice de "
          "qué producto es" % d)


# ─────────────────────────────────────────────────────────────────────────────
# desglosar(): de facturas de Syntage a montos por mes y categoría
# ─────────────────────────────────────────────────────────────────────────────
FACTURAS = [
    # Factura de dispersión con comisión adentro: el monto que cuenta es el
    # del CONCEPTO, nunca el subtotal de la factura completa. Y los $100,000
    # dispersados son fondeo —el dinero— no un cargo.
    {"uuid": "f1", "type": "I", "issuedAt": "2026-03-15 12:00:00", "subtotal": 110300.0,
     "items": [{"description": "DISPERSION", "totalAmount": 100000.0},
               {"description": "CARGO DE COMISION", "totalAmount": 9000.0},
               {"description": "ENVIO", "totalAmount": 1300.0}]},
    # Fondeo separado por producto: solo una parte es combustible.
    {"uuid": "f6", "type": "I", "issuedAt": "2026-03-18 12:00:00", "subtotal": 300000.0,
     "items": [{"description": "GASOLINA MAGNA FLEET CARGA DE SALDOS",
                "totalAmount": 100000.0},
               {"description": "MAS DESPENSA CARGA DE SALDOS",
                "totalAmount": 200000.0}]},
    # El renglón que declara cero: ni suma comisión ni suma otros cargos.
    {"uuid": "f2", "type": "I", "issuedAt": "2026-03-20 12:00:00", "subtotal": 1.0,
     "items": [{"description": "NO EXISTE COMISION POR RAZONES COMERCIALES",
                "totalAmount": 1.0}]},
    {"uuid": "f3", "type": "I", "issuedAt": "2026-04-10 12:00:00", "subtotal": 2500.0,
     "items": [{"description": "SERVICIO ADMINISTRATIVO", "totalAmount": 1812.0},
               {"description": "Comisión", "totalAmount": 688.0}]},
    # Un Complemento de Pago (type P) no es un cargo nuevo: es el recibo de
    # algo ya facturado. Contarlo duplicaría la comisión.
    {"uuid": "f4", "type": "P", "issuedAt": "2026-04-20 12:00:00", "subtotal": 9000.0,
     "items": [{"description": "Pago", "totalAmount": 9000.0}]},
    # Una nota de crédito (type E) tampoco: cancela, no cobra.
    {"uuid": "f5", "type": "E", "issuedAt": "2026-04-25 12:00:00", "subtotal": 500.0,
     "items": [{"description": "ANUALIDAD", "totalAmount": 500.0}]},
]

d = cm.desglosar(FACTURAS)

check(sorted(d["meses"]) == ["2026-03", "2026-04"],
      "los meses que aparecen: %r" % sorted(d["meses"]))
check(d["meses"]["2026-03"]["explicita"] == 9000.0,
      "marzo: $9,000 de comisión explícita, no los $110,300 de la factura: %r"
      % d["meses"]["2026-03"]["explicita"])
check(d["meses"]["2026-03"]["administrativa"] == 0.0,
      "marzo: la dispersión NO es un cargo administrativo: %r"
      % d["meses"]["2026-03"]["administrativa"])
check(d["meses"]["2026-03"]["fondeo"] == 400000.0,
      "marzo: el fondeo son los $100,000 dispersados más los $300,000 de "
      "carga de saldos: %r" % d["meses"]["2026-03"]["fondeo"])
check(d["meses"]["2026-03"]["fondeo_combustible"] == 100000.0,
      "marzo: de ese fondeo, solo $100,000 es gasolina — el resto es "
      "despensa, y su comisión no se le puede achacar al combustible: %r"
      % d["meses"]["2026-03"]["fondeo_combustible"])
check(d["meses"]["2026-03"]["otros"] == 1300.0,
      "marzo: el envío va a otros cargos: %r" % d["meses"]["2026-03"]["otros"])
check(d["meses"]["2026-04"]["explicita"] == 688.0 and
      d["meses"]["2026-04"]["administrativa"] == 1812.0,
      "abril: %r" % d["meses"]["2026-04"])
check(d["meses"]["2026-04"]["otros"] == 0.0,
      "abril: la anualidad venía en una nota de crédito, no cuenta: %r"
      % d["meses"]["2026-04"]["otros"])
check(d["declara_cero"] == 1,
      "se cuenta cuántas veces el monedero declaró que no cobra comisión: %r"
      % d["declara_cero"])

check(d["total"]["explicita"] == 9688.0, "total explícita: %r" % d["total"]["explicita"])
check(d["total"]["administrativa"] == 1812.0,
      "total administrativa: solo el servicio administrativo, sin la "
      "dispersión: %r" % d["total"]["administrativa"])
check(d["total"]["otros"] == 1300.0, "total otros: %r" % d["total"]["otros"])
check(d["total"]["fondeo"] == 400000.0, "total fondeo: %r" % d["total"]["fondeo"])
check(d["total"]["fondeo_combustible"] == 100000.0,
      "total fondeo de combustible: %r" % d["total"]["fondeo_combustible"])

# La cifra que sirve para comparar pricing: los cargos sobre el dinero
# movido, que es como cobra un monedero. Todos los cargos son $12,800
# (comisión $11,500 + envío $1,300) sobre $400,000 de fondeo = 3.2%.
check(abs(d["pct_sobre_fondeo"] - 12800.0 / 400000.0) < 1e-9,
      "el %% de TODOS los cargos sobre el fondeo: %r" % d["pct_sobre_fondeo"])
check(abs(d["pct_comision_sobre_fondeo"] - 11500.0 / 400000.0) < 1e-9,
      "y el de comisión (explícita + administrativa) sobre el fondeo: %r"
      % d["pct_comision_sobre_fondeo"])
check(abs(d["proporcion_combustible"] - 0.25) < 1e-9,
      "qué parte del fondeo es combustible ($100k de $400k): %r"
      % d["proporcion_combustible"])

# El desglose por concepto es lo que hace auditable la clasificación: quien
# lea el Excel puede ver QUÉ se contó como comisión, en vez de creerle a un
# solo número.
conceptos = {c["descripcion"]: c for c in d["conceptos"]}
check(conceptos["CARGO DE COMISION"]["monto"] == 9000.0
      and conceptos["CARGO DE COMISION"]["categoria"] == "explicita",
      "el desglose por concepto: %r" % conceptos.get("CARGO DE COMISION"))
check(conceptos["SERVICIO ADMINISTRATIVO"]["veces"] == 1,
      "cuántas veces se facturó cada concepto: %r"
      % conceptos["SERVICIO ADMINISTRATIVO"])
check("Pago" not in conceptos,
      "los conceptos de un Complemento de Pago no aparecen: %r" % list(conceptos))


# ── El mes sale de issuedAt en hora de México, no del string UTC ───────────
# Mismo criterio que estaciones_monedero._mes_facturacion(): Syntage entrega
# issuedAt en UTC, y una factura emitida a las 23:59:59 hora local del último
# día del mes cae, en UTC, en el primer minuto del mes siguiente.
d_frontera = cm.desglosar([
    {"uuid": "g1", "type": "I", "issuedAt": "2026-05-01 05:59:59", "subtotal": 100.0,
     "items": [{"description": "COMISION", "totalAmount": 100.0}]}])
check(list(d_frontera["meses"]) == ["2026-04"],
      "una factura de las 23:59:59 del 30 de abril (05:59:59 UTC del 1 de mayo) "
      "es de abril, no de mayo: %r" % list(d_frontera["meses"]))


# ── Un monedero sin facturas no truena ────────────────────────────────────
vacio = cm.desglosar([])
check(vacio["meses"] == {} and vacio["total"]["explicita"] == 0.0,
      "sin facturas, forma vacía: %r" % vacio)


# ─────────────────────────────────────────────────────────────────────────────
# recolectar(): una llamada por (cliente, monedero), con caché en disco
# ─────────────────────────────────────────────────────────────────────────────
CARPETA = tempfile.mkdtemp(prefix="_prueba_comisiones_")

llamadas = []


class _SyntageFalso(object):
    @staticmethod
    def id_entidad(rfc):
        return "eid-" + rfc

    @staticmethod
    def facturas(entidad_id, rfc_emisor):
        llamadas.append((entidad_id, rfc_emisor))
        return FACTURAS


_original = cm.syntage
cm.syntage = _SyntageFalso

PARES = [("CLI010101AA1", "MON020202BB2")]
r1 = cm.recolectar(PARES, carpeta=CARPETA)
check(len(llamadas) == 1, "una sola llamada a Syntage por par: %r" % llamadas)
check(r1[("CLI010101AA1", "MON020202BB2")]["total"]["explicita"] == 9688.0,
      "recolectar() devuelve el desglose: %r"
      % r1[("CLI010101AA1", "MON020202BB2")]["total"])

# Segunda corrida: el caché evita volver a pegarle a la API. Importa porque
# un solo cliente grande tiene 909 facturas y el barrido completo tarda.
r2 = cm.recolectar(PARES, carpeta=CARPETA)
check(len(llamadas) == 1,
      "la segunda corrida sale del caché, sin llamar a Syntage: %r" % llamadas)
check(r2 == r1, "y devuelve exactamente lo mismo")

r3 = cm.recolectar(PARES, carpeta=CARPETA, refrescar=True)
check(len(llamadas) == 2, "refrescar=True sí vuelve a llamar: %r" % llamadas)

# ── Un caché de una versión anterior se ignora, no se cree ────────────────
# Pasó de verdad: se cambió la clasificación (se separó el fondeo de los
# cargos) y el caché en disco seguía teniendo el desglose viejo. Leerlo
# habría producido porcentajes equivocados sin un solo aviso.
ruta_cache = os.path.join(CARPETA, "CLI010101AA1_MON020202BB2.json")
with open(ruta_cache, encoding="utf-8") as fh:
    viejo = json.load(fh)
viejo["version"] = cm.VERSION_CACHE - 1
viejo["total"]["explicita"] = 999999.0
with open(ruta_cache, "w", encoding="utf-8") as fh:
    json.dump(viejo, fh)

r5 = cm.recolectar(PARES, carpeta=CARPETA)
check(len(llamadas) == 3,
      "un caché de versión anterior se vuelve a pedir a Syntage: %r" % llamadas)
check(r5[("CLI010101AA1", "MON020202BB2")]["total"]["explicita"] == 9688.0,
      "y NO se usan sus números viejos: %r"
      % r5[("CLI010101AA1", "MON020202BB2")]["total"]["explicita"])

archivos = os.listdir(CARPETA)
check(archivos == ["CLI010101AA1_MON020202BB2.json"],
      "el caché es un archivo por par, con nombre legible: %r" % archivos)
with open(os.path.join(CARPETA, archivos[0]), encoding="utf-8") as fh:
    guardado = json.load(fh)
check(guardado["total"]["explicita"] == 9688.0,
      "el caché guarda el desglose ya calculado: %r" % guardado["total"])


# ── Un cliente que Syntage no conoce se anota, no tumba el barrido ─────────
class _SyntageQueFalla(object):
    @staticmethod
    def id_entidad(rfc):
        raise LookupError("no está dado de alta")

    @staticmethod
    def facturas(entidad_id, rfc_emisor):           # pragma: no cover
        raise AssertionError("no debería llegar aquí")


cm.syntage = _SyntageQueFalla
r4 = cm.recolectar([("NADIE0000XX1", "MON020202BB2")],
                   carpeta=tempfile.mkdtemp(prefix="_prueba_comisiones_2_"))
entrada = r4[("NADIE0000XX1", "MON020202BB2")]
check(entrada["error"] is not None,
      "un cliente que Syntage no conoce queda con el motivo anotado: %r" % entrada)
check(entrada["total"]["explicita"] == 0.0,
      "y con totales en cero, no con basura: %r" % entrada["total"])

cm.syntage = _original
shutil.rmtree(CARPETA, ignore_errors=True)


print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
