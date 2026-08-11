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

# ── el cliente de WeeTrust: los cortes y el nivel de verificacion ────────────
print("WeeTrust")
import weetrust

p = firma.plan(manifiesto("contrato", "adenda_os_pm", "beneficiario_controlador",
                          "pld_pm", "domiciliacion"))
# Sin unir el PDF no hay paginas; se simulan para probar el calculo del corte.
paginas = {"Contrato y obligación solidaria": (1, 13),
           "Identificación del cliente": (14, 18),
           "Autorización de domiciliación": (19, 20)}
for d in p["divisiones"]:
    d["pagina_inicial"], d["pagina_final"] = paginas[d["division"]]

cortes = weetrust.paginas_de_corte(p)
check(cortes == [14, 19],
      "el corte va en la primera pagina de cada division a partir de la segunda")
check(1 not in cortes,
      "y nunca en la pagina 1: el documento ya empieza ahi")

s = weetrust.firmantes_de(p["divisiones"][0])
cliente = next(x for x in s if x["name"] == "JUAN PEREZ GARCIA")
nea = next(x for x in s if x["name"] == "Marcos Siqueiros Ballesteros")
check(cliente.get("identification") == "face" and cliente.get("check") is True,
      "el cliente lleva identification=face con check=true (background check)")
check("identification" not in nea and "check" not in nea,
      "y Nea no lleva verificacion: firma simple")

# LO IMPORTANTE: el camino de borrador no puede enviar, y enviar exige una
# confirmacion literal. Enviar es la unica accion del proyecto cuyo efecto le
# llega a alguien fuera de la empresa y no se deshace.
import inspect
import weetrust as _wt

# El docstring de subir_borrador SI menciona signatory y disableMailing: explica
# por que no los usa. Se revisa el cuerpo, no la documentacion, o la prueba
# castiga justo el comentario que hace falta.
_fuente = inspect.getsource(_wt.subir_borrador)
_cuerpo = _fuente.split('"""')[2] if _fuente.count('"""') >= 2 else _fuente
check("signatory" not in _cuerpo,
      "subir_borrador no llama a /documents/signatory: no puede sacar de borrador")
check("disableMailing" not in _cuerpo,
      "ni usa disableMailing: ese camino no envia aunque alguien se equivoque")

try:
    _wt.enviar_a_firma("x", [{"name": "A", "emailID": "a@b.c"}], "t", "m")
    check(False, "enviar_a_firma sin confirmacion debe negarse")
except _wt.ErrorWeeTrust as e:
    check("confirmacion" in str(e), "enviar_a_firma sin confirmacion se niega")

try:
    _wt.enviar_a_firma("x", [{"name": "A", "emailID": "a@b.c"}], "t", "m",
                       confirmacion=True)
    check(False, "un booleano no debe alcanzar como confirmacion")
except _wt.ErrorWeeTrust:
    check(True, "y un booleano no alcanza: hay que escribir la palabra")

try:
    _wt.enviar_a_firma("x", [{"name": "A", "emailID": "a@b.c"},
                             {"name": "B", "emailID": "a@b.c"}],
                       "t", "m", confirmacion=_wt.CONFIRMACION)
    check(False, "dos firmantes con el mismo correo deben rechazarse antes de llamar")
except _wt.ErrorWeeTrust as e:
    check("comparten correo" in str(e),
          "dos firmantes con el mismo correo se rechazan antes de llamar a la API")

try:
    _wt.enviar_a_firma("x", [{"name": "SIN CORREO"}], "t", "m",
                       confirmacion=_wt.CONFIRMACION)
    check(False, "un firmante sin correo debe detener el envio")
except _wt.ErrorWeeTrust as e:
    check("Sin correo" in str(e), "y un firmante sin correo detiene el envio")

print("El correo, corregido")
m = firma.mensaje(exp)
check("activamos sus tarjetas" not in m, "ya no promete activar tarjetas el mismo dia")
check("representante comercial se pondrá en contacto" in m,
      "y anuncia que el representante comercial agenda la capacitacion")
check("Equipo Nea" in m and "Nea Card" not in m, "firma como Equipo Nea")
