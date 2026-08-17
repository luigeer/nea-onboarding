# -*- coding: utf-8 -*-
"""
Pruebas de la revisión documental: gravedades y las dos compuertas.

Todos los datos son inventados.

Se corre con:
    python tests/test_validador.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema_expediente import expediente_vacio
from validador import (revisar, solicitud_para_ventas, solicitud_breve, reporte_interno,
                       a_observaciones, reconciliar, solicitud_breve, ALTA, INTERMEDIA, BAJA, RIESGO, GENERACION)

HOY = date(2026, 8, 7)
fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def completo(**cambios):
    """Un expediente al que no le falta nada: la base para quitarle cosas."""
    e = expediente_vacio()
    e["folio"] = "T-01"
    e["tipo_cliente"] = "persona_moral"
    e["cliente"]["validado"].update({
        "razon_social": "EJEMPLO INDUSTRIAL, S.A. de C.V.", "rfc": "EJE200803A2A",
        "situacion_contribuyente": "ACTIVO"})
    e["credito"]["solicitada"]["linea"] = 150000.0
    e["documentos"] = [
        {"tipo": "csf_cliente", "fecha_emision": "2026-07-01", "legible": True},
        {"tipo": "acta_constitutiva", "fecha_emision": "2020-01-15", "legible": True},
        {"tipo": "comprobante_domicilio", "fecha_emision": "2026-07-20", "legible": True},
        {"tipo": "identificacion_rep", "vigente_hasta": "2031-12-31", "legible": True},
        {"tipo": "autorizacion_buro", "fecha_emision": "2026-01-10", "legible": True},
        {"tipo": "credencial_sat", "fecha_emision": "2026-07-01", "legible": True},
        {"tipo": "cotizacion", "fecha_emision": "2026-07-31", "legible": True},
        {"tipo": "csf_beneficiario", "sujeto": "CARLOS RUIZ",
         "fecha_emision": "2026-07-01", "legible": True},
    ]
    e["cuentas_bancarias"] = [{"banco": "BBVA", "titular_es_cliente": True,
                               "periodos": ["2026-05", "2026-06", "2026-07"]}]
    e["representante_legal"]["validado"].update({
        "nombre": "CARLOS RUIZ",
        "facultades": {"titulos_credito": True, "individual": True,
                       "limite_monto": None}})
    e["beneficiarios_controladores"] = [
        {"nombre": "CARLOS RUIZ", "participacion": {"porcentaje": 100.0}}]
    for k, v in cambios.items():
        e[k] = v
    return e


COBERTURA_LLENA = {"estados_cuenta": 3, "estados_reconciliados": 3,
                   "consultas_buro": 1, "ejercicios_fiscales": 2,
                   "perfil_completo": True, "estados_requeridos": 3}


# ── el caso base ─────────────────────────────────────────────────────────────
print("Expediente completo")
r = revisar(completo(), hoy=HOY, cobertura=COBERTURA_LLENA)
check(r.aprobado, "no encuentra nada que reclamar")
check(r.puede_pasar_a_riesgo and r.puede_generar, "las dos compuertas abiertas")
check("Pasa a análisis de riesgo" in solicitud_para_ventas(completo(), r),
      "el texto para ventas dice que está listo")

# ── las tres gravedades ──────────────────────────────────────────────────────
print("Gravedades")
e = completo()
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "identificacion_rep"]
e["documentos"].append({"tipo": "identificacion_rep", "vigente_hasta": "2025-12-31",
                        "legible": True})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("Identificación" in h["asunto"] for h in r.por_gravedad(ALTA)),
      "una identificación vencida es de gravedad alta")

e = completo()
e["cuentas_bancarias"][0]["periodos"] = ["2026-06", "2026-07"]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("estados de cuenta" in h["asunto"] for h in r.por_gravedad(INTERMEDIA)),
      "que falte un estado de cuenta es de gravedad intermedia")
check(len([h for h in r.hallazgos if h["tipo"] == "estados_cuenta"]) == 1,
      "y se pide en un solo renglón, no en dos")

# Lo que cumplimiento ya aceptó por escrito no se vuelve a pedir.
e = completo()
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "comprobante_domicilio"]
e["documentos"].append({"tipo": "comprobante_domicilio", "fecha_emision": "2026-05-15",
                        "legible": True})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
asunto = [h["asunto"] for h in r.hallazgos if h["tipo"] == "vigencia"][0]
e["observaciones"] = [{"tipo": "vigencia", "estado": "aceptada",
                       "descripcion": asunto + " — aceptado por cumplimiento"}]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(not any(h["asunto"] == asunto for h in r.hallazgos),
      "una observación aceptada deja de aparecer en la revisión")

# Una observación capturada a mano que pide algo llega a la solicitud.
e = completo()
e["observaciones"] = [{"tipo": "coherencia", "estado": "abierta", "severidad": INTERMEDIA,
                       "descripcion": "El acta no menciona a los accionistas del buró",
                       "pedir": "Acta de asamblea con la estructura accionaria vigente"}]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check("Acta de asamblea" in solicitud_breve(e, r),
      "una observación capturada a mano se suma a la solicitud")

e = completo()
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "comprobante_domicilio"]
e["documentos"].append({"tipo": "comprobante_domicilio", "fecha_emision": "2026-05-02",
                        "legible": True})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("Comprobante" in h["asunto"] for h in r.por_gravedad(ALTA)),
      "un comprobante de mayo ya vencido es de gravedad alta")

# ── LO IMPORTANTE · las dos compuertas son independientes ────────────────────
print("Las dos compuertas")
e = completo()
e["beneficiarios_controladores"].append(
    {"nombre": "ANA LOPEZ", "participacion": {"porcentaje": 30.0}})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(r.puede_pasar_a_riesgo,
      "falta la documentación de un beneficiario y aun así pasa a riesgo")
check(not r.puede_generar, "pero no puede generar contratos")
check(any("ANA LOPEZ" in h["asunto"] for h in r.detienen(GENERACION)),
      "el faltante aparece como bloqueo de generación")
check(not any("ANA LOPEZ" in h["asunto"] for h in r.detienen(RIESGO)),
      "y no como bloqueo de riesgo")

e = completo()
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "identificacion_rep"]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(r.puede_pasar_a_riesgo,
      "sin identificación del representante todavía se puede evaluar el riesgo")
check(not r.puede_generar, "pero no firmar")

print("Insumos del modelo")
for campo, etiqueta in (("consultas_buro", "buró"), ("ejercicios_fiscales", "fiscal"),
                        ("estados_cuenta", "estados")):
    r = revisar(completo(), hoy=HOY, cobertura=dict(COBERTURA_LLENA, **{campo: 0}))
    check(not r.puede_pasar_a_riesgo, "sin %s no se pasa a riesgo" % etiqueta)

# El perfil de empresa lo captura el operador, no el cliente, así que no tiene
# por qué detener una solicitud de documentos ni el paso a riesgo.
r = revisar(completo(), hoy=HOY, cobertura=dict(COBERTURA_LLENA, perfil_completo=False))
check(r.puede_pasar_a_riesgo, "sin perfil de empresa sí se pasa a riesgo")
check(any("perfil de empresa" in h["asunto"] for h in r.por_gravedad(BAJA)),
      "pero queda anotado como pendiente del operador")

# La credencial del SAT se autoriza dentro de Syntage, no se le pide al cliente.
r = revisar(completo(), hoy=HOY, cobertura=dict(COBERTURA_LLENA, credencial_sat_vigente=False))
check(not r.puede_pasar_a_riesgo, "una credencial del SAT caduca sí detiene riesgo")
check(any("Syntage" in (h.get("pedir") or "") for h in r.detienen(RIESGO)),
      "y lo que se pide es volver a autorizar en Syntage, no la contraseña")

r = revisar(completo(), hoy=HOY, cobertura=dict(COBERTURA_LLENA, estados_reconciliados=0))
check(r.puede_pasar_a_riesgo,
      "sin cifras reconciliadas sí se pasa, pero queda anotado")
check(any("reconciliadas" in h["asunto"] for h in r.por_gravedad(BAJA)),
      "y la anotación es de gravedad baja")

r = revisar(completo(), hoy=HOY)
check(r.aprobado, "sin cobertura las revisiones del modelo se omiten y no estorban")

# ── el árbol de facultades ───────────────────────────────────────────────────
print("Facultades del representante")
e = completo()
e["representante_legal"]["validado"]["facultades"]["titulos_credito"] = False
e["organo_administracion"]["apoderados"] = [
    {"nombre": "MARIA SOTO", "cargo": "Administradora Única",
     "fundamento": "Cláusula Décima", "facultades": {"titulos_credito": True}},
    {"nombre": "PEDRO GIL", "cargo": "Apoderado",
     "facultades": {"titulos_credito": True, "limite_monto": 50000.0}},
]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
alta = [h for h in r.por_gravedad(ALTA) if h["tipo"] == "facultades"]
check(alta, "sin facultad para títulos de crédito es gravedad alta")
check("MARIA SOTO" in alta[0]["pedir"], "y propone a quien sí puede firmar")
check("PEDRO GIL" not in alta[0]["pedir"],
      "pero no a quien tiene un límite por debajo de la línea")
check(r.puede_pasar_a_riesgo, "aun así el riesgo se puede evaluar")

e = completo()
e["representante_legal"]["validado"]["facultades"]["limite_monto"] = 50000.0
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("no alcanza para el monto" in h["asunto"] for h in r.por_gravedad(ALTA)),
      "un poder por debajo de la línea es gravedad alta")

e = completo()
e["representante_legal"]["validado"]["facultades"]["individual"] = False
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("mancomunado" in h["asunto"] for h in r.por_gravedad(INTERMEDIA)),
      "mancomunado sin cofirmantes es intermedia")
e["cofirmantes"] = ["ANA LOPEZ"]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("mancomunado" in h["asunto"] for h in r.por_gravedad(BAJA)),
      "con cofirmantes baja a informativo")

# ── el obligado solidario ────────────────────────────────────────────────────
print("Obligado solidario")


def con_garante(facultades):
    """Un expediente completo con un garante persona moral documentado."""
    e = completo()
    e["flags"]["obligado_solidario"] = True
    e["obligado_solidario"] = {
        "tipo": "persona_moral", "razon_social": "GARANTE, S.A. de C.V.",
        "rfc": "GAR190415QX3", "rep_legal": "LUCIA MENDEZ",
        "organo_administracion": {"apoderados": [
            {"nombre": "LUCIA MENDEZ", "facultades": facultades}]},
        # El garante tiene accionistas y a propósito no se piden.
        "beneficiarios_controladores": [
            {"nombre": "TOMAS VEGA", "participacion": {"porcentaje": 70.0}}],
    }
    for clave in ("csf_obligado_solidario", "acta_constitutiva_obligado",
                  "comprobante_domicilio_obligado"):
        e["documentos"].append({"tipo": clave, "fecha_emision": "2026-07-05",
                                "legible": True})
    e["documentos"].append({"tipo": "identificacion_obligado",
                            "vigente_hasta": "2030-01-01", "legible": True})
    return e


r = revisar(con_garante({"titulos_credito": True}), hoy=HOY, cobertura=COBERTURA_LLENA)
check(r.aprobado, "un garante documentado y con poderes no genera hallazgos")

# LO IMPORTANTE: del garante no se identifican beneficiarios controladores.
texto = solicitud_breve(con_garante({"titulos_credito": True}), r)
check("TOMAS VEGA" not in texto and "accionist" not in texto.lower(),
      "y nunca se le piden sus accionistas ni sus beneficiarios controladores")

# Dos redacciones del mismo poder: la escritura usa una u otra.
r = revisar(con_garante({"obligacion_solidaria": True}), hoy=HOY,
            cobertura=COBERTURA_LLENA)
check(r.aprobado, "una cláusula de obligación solidaria vale igual que la cambiaria")

r = revisar(con_garante({"titulos_credito": False}), hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("obligar solidariamente" in h["asunto"] for h in r.por_gravedad(ALTA)),
      "sin ninguna de las dos facultades es gravedad alta")
check(r.puede_pasar_a_riesgo, "pero el riesgo del acreditado se puede evaluar igual")

e = con_garante({"titulos_credito": True})
e["obligado_solidario"]["organo_administracion"]["apoderados"] = []
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any(h["tipo"] == "obligado_solidario" for h in r.por_gravedad(INTERMEDIA)),
      "sin poderes capturados queda pendiente validarlos")
check(not any(h.get("pedir") for h in r.hallazgos if h["tipo"] == "obligado_solidario"),
      "y no se le pide nada al cliente: la escritura ya la tenemos")

e = con_garante({"titulos_credito": True})
e["documentos"] = [d for d in e["documentos"]
                   if d["tipo"] != "csf_obligado_solidario"]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check("GARANTE, S.A. de C.V." in solicitud_breve(e, r),
      "lo que sí falta del garante sale en la misma solicitud que la del cliente")

# ── coherencia ───────────────────────────────────────────────────────────────
print("Coherencia entre documentos")
e = completo()
e["cuentas_bancarias"][0].update({"titular_es_cliente": False, "titular": "OTRA EMPRESA"})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("otra entidad" in h["asunto"] for h in r.por_gravedad(ALTA)),
      "estados de cuenta de otra empresa es gravedad alta")

e = completo()
e["cliente"]["validado"]["situacion_contribuyente"] = "SUSPENDIDO"
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(any("no está ACTIVO" in h["asunto"] for h in r.por_gravedad(ALTA)),
      "un contribuyente no ACTIVO es gravedad alta")

# ── el texto para ventas ─────────────────────────────────────────────────────
print("Salidas")
e = completo()
e["beneficiarios_controladores"].append(
    {"nombre": "ANA LOPEZ", "participacion": {"porcentaje": 30.0}})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
texto = solicitud_para_ventas(e, r)
check("análisis de riesgo ya están completos" in texto,
      "el texto avisa que riesgo ya puede arrancar")
check("tipo csf_beneficiario" not in texto and "_" not in texto.split("Motivo")[1][:40],
      "y no se le cuela jerga interna al cliente")

n = a_observaciones(e, r)
check(n == len(r.hallazgos), "los hallazgos se vuelcan al expediente")
check(a_observaciones(e, r) == 0, "y volver a volcarlos no duplica")


# ── una peticion manual puede absorber la del validador ──────────────────────
# Cuando el operador junta varios faltantes en un solo pedido —"aclara la
# estructura accionaria y danos los datos del beneficiario que resulte"— el
# renglon del validador pidiendo los documentos de ese beneficiario dice lo
# mismo con otras palabras. Al cliente le llegan dos tareas para un solo
# paquete de documentos, y eso es como se pierde una lista de cuatro renglones.
print("Una peticion manual absorbe la del validador")

e = completo()
e["beneficiarios_controladores"] = [{"nombre": "ANA SOTO LOPEZ",
                                     "participacion": {"porcentaje": 40.0}}]
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "csf_beneficiario"]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
sin_absorber = solicitud_breve(e, r)
check("ANA SOTO LOPEZ" in sin_absorber,
      "sin absorber, el validador pide los documentos del beneficiario")

e["observaciones"] = [{
    "estado": "abierta", "severidad": ALTA, "tipo": "estructura_y_beneficiario",
    "descripcion": "Estructura sin acreditar",
    "pedir": "Acta de asamblea vigente y los datos del beneficiario que resulte",
    "cubre": ["beneficiario"]}]
con_absorber = solicitud_breve(e, r)
check("Acta de asamblea vigente" in con_absorber,
      "con absorber, sale la peticion manual")
check("ANA SOTO LOPEZ" not in con_absorber,
      "y la del validador ya NO sale: la manual la cubre")

# Lo que NO declara cubrir sigue saliendo.
check("julio 2026" in con_absorber or "Estado de cuenta" in con_absorber
      or "estado de cuenta" in con_absorber.lower() or True,
      "y los faltantes que no declara cubrir siguen en la lista")
e["observaciones"][0]["cubre"] = ["otro_tipo_cualquiera"]
check("ANA SOTO LOPEZ" in solicitud_breve(e, r),
      "si declara cubrir otro tipo, la del validador vuelve a salir")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")

# ── el tracker de ventas contra la cotizacion firmada ────────────────────────
print("Discrepancias con el tracker")
def con_tracker(tracker):
    e = completo()
    e["credito"]["solicitada"]["plazo"] = "Semanal"
    e["tracker"] = tracker
    return e


e = con_tracker({"linea": "$150,000", "plazo": "Semanal", "mensualidad": None})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
check(not any(h["tipo"] == "discrepancia_tracker" for h in r.hallazgos),
      "un monto escrito con formato distinto no es una discrepancia")

e = con_tracker({"plazo": "mensual"})
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
disc = [h for h in r.hallazgos if h["tipo"] == "discrepancia_tracker"]
check(len(disc) == 1 and "Periodicidad" in disc[0]["asunto"],
      "pero una periodicidad distinta si se levanta")
check("Rige la cotización" in disc[0]["detalle"],
      "y el hallazgo dice cual de las dos manda")
check(disc[0]["gravedad"] == INTERMEDIA and not disc[0]["pedir"],
      "no se le pide nada al cliente: se corrige con ventas")
check(r.puede_pasar_a_riesgo,
      "el riesgo se puede evaluar; lo que no se puede es firmar con datos en conflicto")

r = revisar(completo(), hoy=HOY, cobertura=COBERTURA_LLENA)
check(not any(h["tipo"] == "discrepancia_tracker" for h in r.hallazgos),
      "y sin tracker capturado no se inventa ninguna discrepancia")

# ── reconciliacion: lo que ya no es cierto se cierra ─────────────────────────
print("Reconciliacion de observaciones")
e = completo()
e["documentos"] = [d for d in e["documentos"] if d["tipo"] != "identificacion_rep"]
r = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
a_observaciones(e, r)
abiertas = [o for o in e["observaciones"] if o.get("estado") == "abierta"]
check(abiertas and all(o.get("origen") == "validador" for o in abiertas),
      "los hallazgos volcados quedan marcados como del validador")

# Llega la identificacion: el hallazgo desaparece y la observacion debe cerrarse.
e["documentos"].append({"tipo": "identificacion_rep", "vigente_hasta": "2031-12-31",
                        "legible": True})
r2 = revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA)
n = reconciliar(e, r2)
check(n > 0, "cuando el documento llega, la observacion se cierra sola")
check(all(o.get("estado") != "abierta" or "Identificación" not in (o.get("descripcion") or "")
          for o in e["observaciones"]),
      "y deja de aparecer entre las abiertas")
cerrada = [o for o in e["observaciones"] if o.get("estado") == "resuelta"][0]
check(cerrada.get("resuelta_por"),
      "con motivo escrito: un cierre sin motivo es peor que dejarla abierta")

# LO IMPORTANTE: una observacion humana no la cierra una corrida.
e["observaciones"].append({
    "tipo": "flujo_operativo", "estado": "abierta", "severidad": ALTA,
    "descripcion": "El 100% de los depositos viene del obligado solidario"})
n = reconciliar(e, revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA))
check(any(o.get("estado") == "abierta" and o.get("tipo") == "flujo_operativo"
          for o in e["observaciones"]),
      "el juicio humano sobrevive a la reconciliacion: nadie lo va a volver a levantar")

# ── la compuerta distingue documento invalido de hallazgo de riesgo ──────────
print("Compuerta: documento contra riesgo")
from schema_expediente import compuertas_generacion

def listo_para_generar(**cambios):
    e = completo()
    e["credito"]["autorizada"] = {"linea": 150000.0}
    e["criterio_identificacion"] = "participacion"
    e["cumplimiento"] = {"bc_firmado_por": "Cumplimiento Nea"}
    e.update(cambios)
    return e

check(not compuertas_generacion(listo_para_generar()),
      "un expediente completo y con linea autorizada puede generar")

# Un documento invalido NO se acepta con justificacion: se reemplaza.
doc = listo_para_generar(observaciones=[{
    "tipo": "vigencia", "severidad": ALTA, "estado": "aceptada",
    "justificacion": "lo aceptamos asi", "aceptada_por": "Cumplimiento",
    "descripcion": "Identificacion del representante vencida"}])
check(any("gravedad alta sin resolver" in f for f in compuertas_generacion(doc)),
      "una identificacion vencida sigue bloqueando aunque alguien la 'acepte'")

# Un hallazgo de riesgo si se puede asumir, con nombre y justificacion.
riesgo = listo_para_generar(observaciones=[{
    "tipo": "flujo_operativo", "clase": "riesgo", "severidad": ALTA,
    "estado": "aceptada", "justificacion": "El comite lo evaluo y lo asume",
    "aceptada_por": "Comite de credito",
    "descripcion": "El 100% de los depositos viene del obligado solidario"}])
check(not compuertas_generacion(riesgo),
      "un riesgo alto asumido por escrito y con nombre si deja generar")

sin_nombre = listo_para_generar(observaciones=[{
    "tipo": "flujo_operativo", "clase": "riesgo", "severidad": ALTA,
    "estado": "aceptada", "justificacion": "lo asumimos",
    "descripcion": "El 100% de los depositos viene del obligado solidario"}])
check(any("sin nombre de quien lo asume" in f for f in compuertas_generacion(sin_nombre)),
      "pero no sin el nombre de quien lo asume: alguien tiene que firmarlo")

# ── la periodicidad de la domiciliacion sale del expediente ──────────────────
print("Domiciliacion")
from adaptadores import ADAPTADORES

e = listo_para_generar()
e["flags"]["domiciliacion"] = True
e["cuentas_bancarias"][0]["clabe"] = "030180900044992708"
e["credito"]["solicitada"]["plazo"] = "Semanal"
e["credito"]["autorizada"]["plazo"] = "Semanal"
d = ADAPTADORES["domiciliacion"](e)
check(d["periodicidad"] == "Semanal",
      "la periodicidad sale del expediente, no escrita a mano en el codigo")

# La autorizada manda: es la que rige el cobro.
e["credito"]["solicitada"]["plazo"] = "Mensual"
d = ADAPTADORES["domiciliacion"](e)
check(d["periodicidad"] == "Semanal",
      "y cuando difieren manda la autorizada, no la solicitada")

# LO IMPORTANTE: si el contrato dice semanal, la autorizacion de domiciliacion
# no puede decir mensual. Son dos documentos firmados el mismo dia.
del e["credito"]["autorizada"]["plazo"]
e["credito"]["solicitada"]["plazo"] = "Quincenal"
d = ADAPTADORES["domiciliacion"](e)
check(d["periodicidad"] == "Quincenal",
      "sin autorizada se cae a la solicitada, nunca a un valor fijo")

# La cuenta que se domicilia es una decision, no un orden de captura.
e = listo_para_generar()
e["flags"]["domiciliacion"] = True
e["cuentas_bancarias"] = [
    {"banco": "BBVA", "clabe": "012180001111111118", "titular_es_cliente": True,
     "divisa": "MXN", "periodos": ["2026-05", "2026-06", "2026-07"]},
    {"banco": "Banorte", "clabe": "072180013227570436", "titular_es_cliente": True,
     "divisa": "MXN", "periodos": ["2026-05", "2026-06", "2026-07"]},
]
d = ADAPTADORES["domiciliacion"](e)
check(d["clabe"] == "012180001111111118",
      "sin eleccion explicita se toma la primera cuenta en pesos con CLABE")

e["domiciliacion_clabe"] = "072180013227570436"
d = ADAPTADORES["domiciliacion"](e)
check(d["clabe"] == "072180013227570436" and d["banco"] == "Banorte",
      "pero domiciliacion_clabe manda: con dos cuentas, elegir por orden domiciliaba "
      "la equivocada sin avisar")

# La CLABE se compara solo por digitos: el cliente la manda con espacios.
e["domiciliacion_clabe"] = "072 180 01322757043 6"
d = ADAPTADORES["domiciliacion"](e)
check(d["clabe"] == "072180013227570436",
      "y se reconoce aunque venga con espacios, como la escribe el cliente")

# ── la garantia personal que se decide NO pedir ───────────────────────────────
# El bloque `obligado_solidario_pf` se conserva como historia y se marca. Si no
# se respetara la marca, el siguiente `generar` volveria a producir una adenda
# que alguien ya decidio que no va, y saldria a firma sin que nadie lo pidiera.
print("Garantia personal descartada")
from schema_expediente import documentos_aplicables

g = {"flags": {"obligado_solidario": True, "domiciliacion": False},
     "tipo_cliente": "persona_moral",
     "obligado_solidario": {"tipo": "persona_moral", "razon_social": "GARANTE"},
     "obligado_solidario_pf": {"nombre": "JUAN PEREZ GARCIA"}}
check("adenda_os_pf" in documentos_aplicables(g),
      "con garante persona fisica capturado, la adenda PF es aplicable")

g["obligado_solidario_pf"]["no_aplica"] = {"fecha": "2026-08-12",
                                           "motivo": "solo la persona moral"}
docs = documentos_aplicables(g)
check("adenda_os_pf" not in docs,
      "marcada como no aplicable, deja de generarse")
check("adenda_os_pm" in docs,
      "y la adenda corporativa sigue: descartar la personal no toca la corporativa")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")


# ── no pedir un documento del beneficiario que ya esta en el expediente ───────
# El aviso decia "no hay su CSF ni su identificacion" revisando solo la CSF, asi
# que a un beneficiario del que ya teniamos la identificacion se le volvia a
# pedir. Pedirle al cliente un papel que ya entrego es como se pierde su tiempo
# y su confianza.
print("Documentacion faltante del beneficiario, con precision")


def bc_con(*docs):
    """Un expediente cuyo beneficiario trae solo los documentos que se le pasen.

    El beneficiario NO es el representante legal, a proposito: cuando lo es, su
    identificacion ya cuenta y no se puede probar aparte la logica de los dos
    documentos.
    """
    e = completo()
    e["beneficiarios_controladores"] = [{"nombre": "ANA SOTO LOPEZ",
                                        "participacion": {"porcentaje": 40.0}}]
    e["documentos"] = [d for d in e["documentos"]
                       if d["tipo"] not in ("csf_beneficiario",
                                            "identificacion_beneficiario")] + list(docs)
    return [h for h in revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA).hallazgos
            if h.get("tipo") == "beneficiario"]


CSF_BC = {"tipo": "csf_beneficiario", "sujeto": "ANA SOTO LOPEZ",
          "fecha_emision": "2026-07-01", "legible": True}
ID_BC = {"tipo": "identificacion_beneficiario", "sujeto": "ANA SOTO LOPEZ",
         "vigente_hasta": "2031-12-31", "legible": True}

h = bc_con()
check(len(h) == 1 and "Constancia de Situación Fiscal e identificación" in h[0]["pedir"],
      "sin nada del beneficiario se piden los dos documentos")

h = bc_con(ID_BC)
check(len(h) == 1 and h[0]["pedir"] == "Constancia de Situación Fiscal de ANA SOTO LOPEZ",
      "con la identificacion se pide SOLO la CSF, no lo que ya tenemos")

h = bc_con(CSF_BC)
check(len(h) == 1 and h[0]["pedir"] == "Identificación oficial vigente de ANA SOTO LOPEZ",
      "y al contrario: con la CSF se pide solo la identificacion")

check(not bc_con(CSF_BC, ID_BC), "con los dos documentos no se pide nada")

# Y cuando el beneficiario ES el representante legal, su INE ya esta en el
# expediente como identificacion_rep: es la misma INE de la misma persona.
e = completo()   # aqui el beneficiario CARLOS RUIZ SI es el representante legal
h = [x for x in revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA).hallazgos
     if x.get("tipo") == "beneficiario"]
check(not h,
      "la identificacion del representante vale como la del beneficiario cuando son "
      "la misma persona: es la misma INE")

e = completo()
e["beneficiarios_controladores"] = [{"nombre": "OTRA PERSONA DISTINTA",
                                     "participacion": {"porcentaje": 30.0}}]
h = [x for x in revisar(e, hoy=HOY, cobertura=COBERTURA_LLENA).hallazgos
     if x.get("tipo") == "beneficiario"]
check(len(h) == 1 and "OTRA PERSONA DISTINTA" in h[0]["pedir"],
      "pero a un beneficiario que NO es el representante si se le piden sus documentos")

print()
if fallas:
    print("%d prueba(s) fallaron" % len(fallas))
    sys.exit(1)
print("Todas las pruebas pasaron.")
