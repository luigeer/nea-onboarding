# -*- coding: utf-8 -*-
"""
Pruebas de las reglas de division y de nivel de firma.

Lo que se prueba son reglas de negocio, no formato: que el contrato y las adendas
nunca se separen, que la agrupacion del beneficiario controlador y el PLD dependa
de si hay domiciliacion, y que el nivel de verificacion sea el correcto por rol.
Si una de estas se rompe, el cliente firma un paquete mal armado y nadie lo nota
hasta la ceremonia.

Todos los datos son inventados.

Se corre con:
    python tests/test_firma.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firma

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


CLIENTE = {"rol": "cliente", "nombre": "JUAN PEREZ GARCIA",
           "cargo": "Administrador Único"}
NEA = {"rol": "nea", "nombre": "Marcos Siqueiros Ballesteros",
       "cargo": "Representante Legal"}
CUMPL = {"rol": "cumplimiento", "nombre": "Marcos Siqueiros Ballesteros",
         "cargo": "Oficial de Cumplimiento"}
OS = {"rol": "obligado_solidario", "nombre": "JUAN PEREZ GARCIA",
      "cargo": "Por su propio derecho"}


def manifiesto(*claves):
    firmantes = {
        "contrato": [CLIENTE, NEA],
        "adenda_os_pm": [CLIENTE, OS, NEA],
        "adenda_os_pf": [CLIENTE, OS, NEA],
        "beneficiario_controlador": [CLIENTE, CUMPL],
        "pld_pm": [CLIENTE],
        "domiciliacion": [CLIENTE],
    }
    return {"folio": "T-01", "documentos": [
        {"clave": c, "archivo": "T-01_%s.pdf" % c, "firmantes": firmantes[c]}
        for c in claves]}


def divs(p):
    return [d["division"] for d in p["divisiones"]]


# ── el contrato y las adendas nunca se separan ────────────────────────────────
print("Division del contrato")
p = firma.plan(manifiesto("contrato", "adenda_os_pm", "adenda_os_pf"))
check(len(p["divisiones"]) == 1,
      "contrato y las dos adendas quedan en una sola division")
check(len(p["divisiones"][0]["documentos"]) == 3,
      "con los tres documentos dentro")
check(p["divisiones"][0]["documentos"][0]["clave"] == "contrato",
      "y el contrato va primero: la adenda no significa nada sin el")

# ── la regla del beneficiario controlador y el PLD ────────────────────────────
print("Beneficiario controlador y PLD")
con = firma.plan(manifiesto("contrato", "beneficiario_controlador", "pld_pm",
                            "domiciliacion"))
bc_pld = [d for d in con["divisiones"]
          if len(d["documentos"]) == 2
          and {x["clave"] for x in d["documentos"]} == {"beneficiario_controlador",
                                                       "pld_pm"}]
check(len(bc_pld) == 1,
      "CON domiciliacion, el beneficiario controlador y el PLD van juntos")

sin = firma.plan(manifiesto("contrato", "beneficiario_controlador", "pld_pm"))
juntos = [d for d in sin["divisiones"]
          if {x["clave"] for x in d["documentos"]} == {"beneficiario_controlador",
                                                       "pld_pm"}]
check(not juntos, "SIN domiciliacion van en divisiones separadas")
check(len(sin["divisiones"]) == 3,
      "asi que sin domiciliacion salen tres divisiones y no dos")

check("Autorización de domiciliación" in divs(con),
      "la domiciliacion va en su propia division: esta dirigida al banco")

# ── LO IMPORTANTE · el nivel de verificacion ──────────────────────────────────
print("Nivel de firma")
p = firma.plan(manifiesto("contrato", "beneficiario_controlador"))
todos = [f for d in p["divisiones"] for f in d["firmantes"]]
cliente = [f for f in todos if f["nombre"] == "JUAN PEREZ GARCIA"]
nea = [f for f in todos if f["nombre"] == "Marcos Siqueiros Ballesteros"]
check(cliente and all(f["nivel"] == firma.IDENTIDAD for f in cliente),
      "el representante del cliente firma con verificacion de identidad")
check(nea and all(f["nivel"] == firma.SIMPLE for f in nea),
      "y Nea firma simple: es nuestra propia firma")

# Marcos firma la misma division como representante legal y como oficial de
# cumplimiento: una sola entrada, con los dos roles.
p = firma.plan({"folio": "T-01", "documentos": [
    {"clave": "contrato", "archivo": "a.pdf", "firmantes": [CLIENTE, NEA]},
    {"clave": "adenda_os_pm", "archivo": "b.pdf", "firmantes": [CLIENTE, CUMPL]}]})
marcos = [f for d in p["divisiones"] for f in d["firmantes"]
          if f["nombre"] == "Marcos Siqueiros Ballesteros"]
check(len(marcos) == 1, "una persona que firma dos veces la misma division no se duplica")
check(sorted(marcos[0]["roles"]) == ["cumplimiento", "nea"],
      "y conserva los dos roles con los que firma")

# Si una persona firmara con dos niveles distintos, gana el mas exigente: no se
# puede pedir menos verificacion de la que exige el documento mas estricto.
p = firma.plan({"folio": "T-01", "documentos": [
    {"clave": "contrato", "archivo": "a.pdf",
     "firmantes": [{"rol": "nea", "nombre": "AMBIGUO"}]},
    {"clave": "adenda_os_pm", "archivo": "b.pdf",
     "firmantes": [{"rol": "cliente", "nombre": "AMBIGUO"}]}]})
amb = [f for d in p["divisiones"] for f in d["firmantes"] if f["nombre"] == "AMBIGUO"]
check(amb and amb[0]["nivel"] == firma.IDENTIDAD,
      "y con dos niveles distintos gana el mas exigente")

print("El correo")
exp = {"cliente": {"validado": {"razon_social": "EJEMPLO, S.A. de C.V."}},
       "representante_legal": {"validado": {"nombre": "JUAN PEREZ GARCIA"}},
       "credito": {"autorizada": {"linea": 150000.0, "plazo": "Semanal"}}}
m = firma.mensaje(exp)
check("Juan" in m, "saluda por el nombre de pila")
check("$150,000.00" in m and "semanal" in m,
      "y dice la linea autorizada con su periodicidad")
check("EJEMPLO, S.A. de C.V." in m, "a nombre de la empresa correcta")
check(firma.ASUNTO == "Contrato de Crédito Nea", "el asunto es el que se pidio")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
