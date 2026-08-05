# -*- coding: utf-8 -*-
"""
Pruebas de los mapeos CSF → obligado solidario y CSF → beneficiario controlador.

Los fixtures replican la forma que devuelve extraer_csf(); el parseo del PDF se
prueba aparte contra constancias reales. **Todos los datos de aquí son
inventados**: ningún dato de cliente entra al repositorio.

Se corre con:

    python tests/test_aplicar_csf.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema_expediente import expediente_vacio
from extraer_csf import a_obligado_solidario, a_beneficiario, _curp_datos, _tokens_nombre

DOM = {"calle": "REFORMA", "num_ext": "100", "num_int": None, "colonia": "CENTRO",
       "cp": "06000", "localidad": None, "municipio": "CUAUHTEMOC",
       "estado": "CIUDAD DE MEXICO", "pais": "México", "entre_calle": None,
       "y_calle": None}

CSF_PF = {
    "rfc": "PEGJ850612AB1", "tipo_cliente": "persona_fisica",
    "razon_social": "Juan Pérez García",
    "nombre_registral": "PEREZ GARCIA JUAN",
    "curp": "PEGJ850612HDFRRN04", "nombre_comercial": None,
    "regimen_capital": None, "idcif": "00000000001",
    "fecha_emision": "2026-07-06", "lugar_emision": "CUAUHTEMOC, CIUDAD DE MEXICO",
    "vigente_hasta": "2026-10-06", "inicio_operaciones": "2020-08-03",
    "situacion_contribuyente": "ACTIVO", "domicilio": DOM,
    "actividades": [], "actividad_principal": "Otros servicios de apoyo a los negocios",
    "regimenes": [], "regimen_fiscal": "Sueldos y Salarios", "alertas": [],
}

CSF_PM = {
    "rfc": "EJE200803A2A", "tipo_cliente": "persona_moral",
    "razon_social": "EJEMPLO INDUSTRIAL, S.A. de C.V.", "nombre_registral": None,
    "curp": None, "nombre_comercial": None,
    "regimen_capital": "Sociedad Anónima de Capital Variable", "idcif": "00000000002",
    "fecha_emision": "2026-07-06", "lugar_emision": None,
    "vigente_hasta": "2026-10-06", "inicio_operaciones": "2020-08-03",
    "situacion_contribuyente": "ACTIVO", "domicilio": DOM,
    "actividades": [], "actividad_principal": "Consultoría",
    "regimenes": [], "regimen_fiscal": "General de Ley Personas Morales",
    "alertas": ["CSF vence en 3 día(s), el 2026-10-06."],
}

fallas = []


def check(cond, msg):
    if cond:
        print("  ok  %s" % msg)
    else:
        fallas.append(msg)
        print("FALLA %s" % msg)


# ── CURP ─────────────────────────────────────────────────────────────────────
print("_curp_datos")
d = _curp_datos("PEGJ850612HDFRRN04")
check(d.get("fecha_nacimiento") == "12/06/1985", "siglo XX por dígito 17 numérico")
check(d.get("lugar_nacimiento") == "Ciudad de México", "entidad DF")
d = _curp_datos("AAAA050214MMCRRLA3")
check(d.get("fecha_nacimiento") == "14/02/2005", "siglo XXI por letra en posición 17")
check(d.get("lugar_nacimiento") == "Estado de México", "entidad MC")
check(_curp_datos("PEGJ851312HDFRRN04") == {}, "mes 13 se rechaza")
check(_curp_datos(None) == {} and _curp_datos("BASURA") == {}, "CURP ausente o malformada")

# ── nombres sin importar orden ni acentos ────────────────────────────────────
print("_tokens_nombre")
check(_tokens_nombre("Juan Pérez García") == _tokens_nombre("PEREZ GARCIA JUAN"),
      "CSF contra orden registral")
check(_tokens_nombre("Ana López") != _tokens_nombre("Ana María López"),
      "nombres distintos no se funden")

# ── obligado solidario persona física ────────────────────────────────────────
print("a_obligado_solidario (persona física)")
exp = expediente_vacio()
exp["cliente"]["validado"]["rfc"] = "EJE200803A2A"
puestos = a_obligado_solidario(CSF_PF, exp)
pf = exp["obligado_solidario"]["persona_fisica"]
check(exp["obligado_solidario"]["tipo"] == "persona_fisica", "tipo derivado del RFC")
check(pf["nombre"] == "Juan Pérez García" and pf["curp"] == "PEGJ850612HDFRRN04"
      and pf["rfc"] == "PEGJ850612AB1", "identidad completa")
check(pf["fecha_lugar_nacimiento"] == "12/06/1985, Ciudad de México",
      "fecha y lugar de nacimiento desde la CURP")
check(pf["ocupacion"] == "Otros servicios de apoyo a los negocios",
      "ocupación de la actividad")
check("C.P. 06000" in pf["domicilio"], "domicilio en una línea")
check(exp["flags"]["obligado_solidario"] is False,
      "el flag sigue siendo de riesgo, no se toca")
check(any(d["tipo"] == "csf_obligado_solidario" for d in exp["documentos"]),
      "documento registrado")
check(exp["procedencia"].get("obligado_solidario.curp"), "procedencia por campo")

# no sobreescribe lo validado
exp2 = expediente_vacio()
exp2["obligado_solidario"]["persona_fisica"]["ocupacion"] = "Empresario"
a_obligado_solidario(CSF_PF, exp2)
check(exp2["obligado_solidario"]["persona_fisica"]["ocupacion"] == "Empresario",
      "no sobreescribe campos ya validados")

# ── obligado solidario persona moral ─────────────────────────────────────────
print("a_obligado_solidario (persona moral)")
exp = expediente_vacio()
exp["cliente"]["validado"]["rfc"] = "OTRO000000XXX"
a_obligado_solidario(CSF_PM, exp)
os_ = exp["obligado_solidario"]
check(os_["tipo"] == "persona_moral" and os_["rfc"] == "EJE200803A2A"
      and os_["razon_social"] == "EJEMPLO INDUSTRIAL, S.A. de C.V.", "datos de la moral")
check(any(o["tipo"] == "csf_obligado" and "vence" in o["descripcion"]
          for o in exp["observaciones"]), "las alertas de la CSF pasan a observaciones")

# mismo RFC que el cliente → bloqueante
exp = expediente_vacio()
exp["cliente"]["validado"]["rfc"] = "EJE200803A2A"
a_obligado_solidario(CSF_PM, exp)
check(any(o["severidad"] == "bloqueante" and "sí mismo" in o["descripcion"]
          for o in exp["observaciones"]), "obligado igual al cliente es bloqueante")

# ── beneficiario controlador ─────────────────────────────────────────────────
print("a_beneficiario")
exp = expediente_vacio()
puestos, nuevo = a_beneficiario(CSF_PF, exp)
bc = exp["beneficiarios_controladores"][0]
check(nuevo and len(exp["beneficiarios_controladores"]) == 1, "beneficiario nuevo agregado")
check(bc["participacion"]["porcentaje"] is None, "la participación no sale de una CSF")
check(bc["pais_residencia"] == "México" and bc["lugar_nacimiento"] == "Ciudad de México",
      "residencia y nacimiento")
check(any(o["tipo"] == "beneficiario_controlador" for o in exp["observaciones"]),
      "advertencia de participación pendiente")

# fusión con el listado de la constitutiva, por nombre en otro orden
exp = expediente_vacio()
exp["beneficiarios_controladores"].append({
    "nombre": "PEREZ GARCIA JUAN", "rfc": None, "curp": None,
    "participacion": {"porcentaje": 100.0, "monto": 50000.0},
    "criterio_determinacion": "Fracción I", "ocupacion": None,
})
puestos, nuevo = a_beneficiario(CSF_PF, exp)
bc = exp["beneficiarios_controladores"][0]
check(not nuevo and len(exp["beneficiarios_controladores"]) == 1,
      "se funde con el ya listado aunque el orden del nombre difiera")
check(bc["nombre"] == "PEREZ GARCIA JUAN", "el nombre validado no se pisa")
check(bc["rfc"] == "PEGJ850612AB1" and bc["curp"] == "PEGJ850612HDFRRN04",
      "RFC y CURP se completan")
check(bc["participacion"]["porcentaje"] == 100.0, "la participación existente queda intacta")

# repetir la misma CSF no duplica
puestos2, nuevo2 = a_beneficiario(CSF_PF, exp)
check(not nuevo2 and len(exp["beneficiarios_controladores"]) == 1 and puestos2 == [],
      "reaplicar la misma CSF es inocuo")

# una CSF de persona moral no puede ser beneficiario
try:
    a_beneficiario(CSF_PM, expediente_vacio())
    check(False, "CSF de moral como beneficiario debe rechazarse")
except ValueError:
    check(True, "CSF de moral como beneficiario debe rechazarse")

# ─────────────────────────────────────────────────────────────────────────────
print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
