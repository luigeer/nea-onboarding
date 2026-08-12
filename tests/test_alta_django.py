# -*- coding: utf-8 -*-
"""
Pruebas del armado de campos para el alta manual en el Django operativo.

Lo que se prueba es lo que se puede registrar mal sin que nadie lo note: una
fecha con el día y el mes intercambiados, un nombre partido por el lugar
equivocado, y un dato faltante que se ve igual que un dato vacío a proposito.

Todos los datos son inventados.

Se corre con:
    python tests/test_alta_django.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alta_django as ad

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


# ── las fechas ────────────────────────────────────────────────────────────────
print("Fechas en aaaa-mm-dd")
check(ad.fecha("19/06/1998") == "1998-06-19",
      "dd/mm/aaaa se voltea: es el formato del formato de la UIF")
check(ad.fecha("1998-06-19") == "1998-06-19", "aaaa-mm-dd se deja igual")
check(ad.fecha("8/1/1974") == "1974-01-08", "un solo digito de dia y mes se rellena")
check(ad.fecha("2026-08-12T10:00:00Z") == "2026-08-12", "un timestamp se recorta")
check(ad.fecha("junio 1998") is None,
      "lo que no se entiende devuelve None y sale FALTA, no una fecha inventada")
check(ad.fecha(None) is None, "y un vacio sigue vacio")

# ── LO IMPORTANTE · la particion del nombre ──────────────────────────────────
print("Particion del nombre contra la CURP")
n = ad.partir_nombre("DIEGO RAMIREZ GUTIERREZ", "RAGD980619HDFMTG03")
check((n["nombres"], n["paterno"], n["materno"]) == ("DIEGO", "RAMIREZ", "GUTIERREZ"),
      "el caso simple sale bien")
check(n["comprobado"], "y queda marcado como comprobado contra la CURP")

# Un apellido compuesto. El RENAPO ignora las particulas, asi que "DE LA CRUZ"
# entra a la CURP como CRUZ: C + U (primera vocal interna) + S (SOTO) + M (MARIA).
n = ad.partir_nombre("MARIA DE LA CRUZ SOTO", "CUSM800101MDFXXX01")
check(n["paterno"] == "DE LA CRUZ" and n["materno"] == "SOTO" and n["nombres"] == "MARIA",
      "un apellido compuesto se arma con la CURP, particulas incluidas")
check(n["comprobado"], "y tambien queda comprobado")

# Sin CURP, la convencion tampoco debe dejar "DE LA" del lado de los nombres.
n = ad.partir_nombre("MARIA DE LA CRUZ SOTO")
check(n["paterno"] == "DE LA CRUZ" and n["nombres"] == "MARIA",
      "y sin CURP la convencion absorbe las particulas hacia el apellido")

# El RENAPO toma la inicial del SEGUNDO nombre cuando el primero es MARIA o JOSE.
n = ad.partir_nombre("MARIA GUADALUPE LOPEZ SOTO", "LOSG850101MDFXXX01")
check(n["nombres"] == "MARIA GUADALUPE" and n["paterno"] == "LOPEZ",
      "con MARIA de primer nombre la CURP usa la inicial del segundo")
check(n["comprobado"], "y la particion se comprueba igual")

# Sin apellido materno la CURP lleva X en la tercera posicion.
n = ad.partir_nombre("JUAN PEREZ", "PEXJ900101HDFXXX09")
check(n["paterno"] == "PEREZ" and n["materno"] is None,
      "sin apellido materno no se invita al primer nombre a ocupar su lugar")

# Cuando la CURP NO cuadra, la particion sale pero marcada como no comprobada.
n = ad.partir_nombre("ANA LOPEZ RUIZ", "ZZZZ900101HDFXXX01")
check(not n["comprobado"], "una CURP que no cuadra no se aprueba en silencio")
check("revisar contra la identificación" in n["nota"],
      "y la nota manda a revisar la identificacion oficial")
check(n["paterno"] == "LOPEZ", "aunque el valor propuesto sigue siendo el de la convencion")

n = ad.partir_nombre("ANA LOPEZ RUIZ", None)
check(not n["comprobado"], "sin CURP tampoco se declara comprobada")

# El nombre registral de la CSF viene en orden PATERNO MATERNO NOMBRES.
n = ad.partir_nombre("MARIA GUADALUPE HERNANDEZ", curp="HEXM850101MDFXXX02",
                     registral="HERNANDEZ MARIA GUADALUPE")
check(n["paterno"] == "HERNANDEZ",
      "el nombre registral de la CSF tambien se usa para partir")

# ── los catalogos ─────────────────────────────────────────────────────────────
print("Catalogos del formulario")
check(ad.regimen_fiscal("Régimen General de Ley Personas Morales")
      == "601 General de Ley Personas Morales",
      "el regimen fiscal sale con clave: el dropdown la lleva y la CSF no")
check(ad.regimen_capital("SOCIEDAD ANONIMA DE CAPITAL VARIABLE") == "S.A. de C.V.",
      "y el regimen de capital abreviado")
check(ad.regimen_fiscal("626 Régimen Simplificado de Confianza").startswith("626"),
      "si ya viene con clave se respeta")
check(ad.regimen_fiscal("Un régimen que no existe") is None,
      "un regimen desconocido devuelve None para que se elija a mano")

# ── un expediente completo ────────────────────────────────────────────────────
print("El armado completo")
EXP = {
    "cliente": {"validado": {
        "rfc": "AAA010101AAA", "razon_social": "EJEMPLO, S.A. de C.V.",
        "nombre_comercial": "EJEMPLO", "telefono": "5500000000",
        "regimen_fiscal": "Régimen General de Ley Personas Morales",
        "regimen_capital": "SOCIEDAD ANONIMA DE CAPITAL VARIABLE",
        "actividad_economica": "Comercio al por mayor de abarrotes",
        "domicilio": {"calle": "CALLE FALSA", "num_ext": "123", "num_int": "4",
                      "colonia": "CENTRO", "municipio": "BENITO JUAREZ",
                      "cp": "03100", "estado": "CIUDAD DE MEXICO"}}},
    "constitucion": {"fecha": "2020-01-15"},
    "credito": {"autorizada": {"linea": 50000.0, "autorizada_el": "2026-08-10",
                               "autorizada_por": "Comité", "score": 0.51,
                               "veredicto_modelo": "Comité"}},
    "representante_legal": {"validado": {
        "nombre": "JUAN PEREZ GARCIA", "curp": "PEGJ900101HDFRRN05",
        "rfc": "PEGJ900101AAA", "fecha_nacimiento": "1990-01-01"},
        "propuesto": {"correo": "juan@ejemplo.mx"}},
    "beneficiarios_controladores": [{
        "nombre": "JUAN PEREZ GARCIA", "curp": "PEGJ900101HDFRRN05",
        "rfc": "PEGJ900101AAA", "fecha_nacimiento": "01/01/1990",
        "participacion": {"porcentaje": 100.0},
        "criterio_determinacion": "Fracción I del Art. 32-B Ter CFF"}],
    "organo_administracion": {"administrador": "JUAN PEREZ GARCIA"},
    "obligado_solidario": {"razon_social": "GARANTE, S.A. de C.V.", "rfc": "BBB020202BBB"},
    "domiciliacion_clabe": {"clabe": "072180013227570436", "banco": "Banorte"},
    "tracker": {"origen": "Expo Puebla", "ejecutivo": "Fer Caballero"},
    "firma": {"estado": "completada", "fecha": "2026-08-12"},
    "documentos": [{"tipo": "csf_cliente", "drive_file_id": "abc"}],
    "observaciones": [],
}

secs = ad.secciones(EXP)
check([s["seccion"] for s in secs] == [
    "Empresa", "Dirección de la empresa", "Línea de crédito",
    "Origen de la empresa", "Representante legal #1", "Beneficiario controlador #1"],
    "las seis secciones salen en el orden del formulario")


def campo(sec, etiqueta):
    s = next(x for x in secs if x["seccion"] == sec)
    return next(c for c in s["campos"] if c["etiqueta"] == etiqueta)


check(campo("Empresa", "Fecha de constitución")["valor"] == "2020-01-15",
      "la fecha de constitucion sale normalizada")
check(campo("Empresa", "¿Tiene línea garantizada?")["valor"] is True,
      "con obligado solidario la linea es garantizada")
check("GARANTE" in campo("Empresa", "¿Tiene línea garantizada?")["nota"],
      "y la nota dice quien garantiza")
check(campo("Empresa", "¿Puede operar?")["valor"] is True,
      "firmado, puede operar")
check(campo("Empresa", "CLABE de retiro")["valor"] == "072180013227570436",
      "la CLABE de retiro es la que el cliente autorizo por escrito")
check(campo("Línea de crédito", "Línea de crédito")["valor"] == "50000",
      "la linea va sin decimales ni signo de pesos: es un campo numerico")
check(campo("Beneficiario controlador #1", "Fecha de nacimiento")["valor"] == "1990-01-01",
      "la fecha del beneficiario venia en dd/mm/aaaa y sale en aaaa-mm-dd")

# El campo de archivo trae el link de Drive, no solo el nombre.
csf = campo("Empresa", "Cedula de identificacion fiscal")
check(csf["nota"] and "drive.google.com" in csf["nota"],
      "los campos de archivo traen el link del documento en Drive")

# LO IMPORTANTE: un vinculo que nadie documento no se marca.
v = campo("Beneficiario controlador #1", "Vínculos de Control o Beneficio")["valor"]
check(ad.VINCULOS[0] in v, "la participacion en el capital se marca: esta en el criterio")
check(ad.VINCULOS[2] in v, "y las facultades de decision: esta en el organo de administracion")
check(ad.VINCULOS[3] not in v,
      "pero el beneficio economico final NO se marca: nadie lo documento")

print("Lo que falta se declara")
sin_firma = dict(EXP, firma={"estado": "pendiente"})
avisos = ad.pendientes(sin_firma)
check(any("no están firmados" in a for a in avisos),
      "sin contratos firmados el alta se detiene")

sin_tel = dict(EXP)
sin_tel["cliente"] = {"validado": dict(EXP["cliente"]["validado"], telefono=None)}
avisos = ad.pendientes(sin_tel)
check(any("Teléfono" in a for a in avisos),
      "un dato que falta se enlista; no se pega un campo vacio sin avisar")

# El comprobante de domicilio del beneficiario NO se pide: no es obligatorio y
# la CSF ya trae el domicilio. Si esto vuelve a salir como pendiente, la lista se
# llena de algo que nadie va a conseguir y deja de leerse.
check(not any("Comprobante de Domicilio" in a for a in ad.pendientes(EXP)),
      "el comprobante de domicilio del beneficiario no entra en pendientes")
bc = next(s for s in secs if s["seccion"] == "Beneficiario controlador #1")
cd = next(c for c in bc["campos"] if c["etiqueta"] == "Comprobante de Domicilio")
check(cd["opcional"] and "CSF" in cd["nota"],
      "y sale marcado como vacio a proposito, con el motivo")

alta = dict(EXP, observaciones=[{"estado": "abierta", "severidad": "alta",
                                 "descripcion": "Poder sin facultades"}])
check(any("Observación alta abierta" in a for a in ad.pendientes(alta)),
      "y una observacion alta abierta tambien detiene el alta")

t = ad.texto(EXP)
check("=== Empresa ===" in t and "=== Beneficiario controlador #1 ===" in t,
      "el volcado en texto trae todas las secciones")
check("SÍ (marcar)" in t, "y los checkboxes dicen si se marcan o no")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
