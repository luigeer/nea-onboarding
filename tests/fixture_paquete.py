# -*- coding: utf-8 -*-
"""Expedientes inventados, completos, para generar paquetes reales en pruebas.

No es una prueba: tests/todas.py solo corre archivos test_*.py.
"""

import copy

from schema_expediente import expediente_vacio

_DOMICILIO = {"calle": "CALLE FALSA", "num_ext": "123", "num_int": None,
              "colonia": "CENTRO", "cp": "03100", "municipio": "BENITO JUAREZ",
              "estado": "CIUDAD DE MEXICO", "pais": "Mexico"}


def persona_moral():
    e = expediente_vacio()
    e["folio"] = "T-01"
    e["tipo_cliente"] = "persona_moral"
    e["fechas"]["operacion"] = "2026-09-25"
    e["cliente"]["validado"].update({
        "razon_social": "EJEMPLO INDUSTRIAL, S.A. de C.V.", "rfc": "EJE200803A2A",
        "nombre_comercial": "EJEMPLO", "situacion_contribuyente": "ACTIVO",
        "actividad_economica": "Comercio al por mayor de abarrotes",
        "domicilio": dict(_DOMICILIO), "telefono": "5500000000",
        "correo": "contacto@ejemplo.mx"})
    e["credito"]["solicitada"].update({"linea": 150000.0, "plazo": "Mensual"})
    e["credito"]["autorizada"].update({"linea": 150000.0, "plazo": "Mensual",
                                       "mensualidad": 3200.0, "fecha": "2026-09-25",
                                       "autorizada_por": "Comite"})
    e["constitucion"].update({"fecha": "2020-01-15", "instrumento": "1,234",
                              "fedatario": "Lic. Ejemplo", "notaria": "8",
                              "plaza": "Ciudad de Mexico", "inscripcion_rpc": "N-123",
                              "fecha_inscripcion_rpc": "2020-02-20",
                              "capital_social": 50000.0, "acciones": "100 acciones"})
    e["grit_monedero"].update({"modelo_negocio": "prepago", "comision": "1.25%",
                               "cuota": 0, "costo_tarjeta": 0})
    e["representante_legal"]["validado"].update({
        "nombre": "CARLOS RUIZ LOPEZ", "rfc": "RULC800101AAA",
        "curp": "RULC800101HDFZPR09", "cargo": "Administrador Unico",
        "fecha_nacimiento": "1980-01-01", "pais_nacimiento": "Mexico",
        "pais_nacionalidad": "Mexico",
        "identificacion": {"tipo": "INE", "numero": "1234567890", "vigencia": "2031",
                           "pais_emisor": "Mexico", "autoridad_emisora": "INE"},
        "poder": {"escritura": "1,234", "notario": "Lic. Ejemplo",
                  "notaria": "No. 8, CDMX"},
        "facultades": {"titulos_credito": True, "individual": True,
                       "limite_monto": None}})
    e["cuentas_bancarias"] = [{"banco": "BBVA", "titular_es_cliente": True,
                               "periodos": ["2026-06", "2026-07", "2026-08"]}]
    e["criterio_identificacion"] = "participacion"
    e["cumplimiento"]["bc_firmado_por"] = "Marcos Siqueiros Ballesteros"
    e["estructura_accionaria"] = [{"accionista": "CARLOS RUIZ LOPEZ", "acciones": 100,
                                   "importe": 50000.0, "porcentaje": 100.0}]
    e["beneficiarios_controladores"] = [{
        "nombre": "CARLOS RUIZ LOPEZ", "rfc": "RULC800101AAA",
        "curp": "RULC800101HDFZPR09", "domicilio": dict(_DOMICILIO),
        "fecha_nacimiento": "1980-01-01",
        "identificacion": {"tipo": "INE", "numero": "1234567890", "vigencia": "2031"},
        "participacion": {"porcentaje": 100.0, "monto": 50000.0},
        "criterio_determinacion": "participacion",
        "forma_participacion": "accionista directo", "pep": False}]
    e["organo_administracion"].update({"tipo": "Administrador Unico"})
    e["quien_lleno"] = "Persona De Prueba"
    return e


def copia(exp):
    return copy.deepcopy(exp)
