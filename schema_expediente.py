# -*- coding: utf-8 -*-
"""
schema_expediente.py — Estructura canónica del expediente de onboarding de Nea
===============================================================================
Fuente única de verdad. De aquí salen los ocho generadores de documentos, el
registro de Notion y el modelo de riesgo. Ningún generador se llama con datos
que no hayan pasado por aquí.

Dos principios de diseño:

1. Capas declarado / validado. Lo que teclea ventas y lo que se desprende de un
   documento son campos distintos. Guardar solo el valor final borra la traza de
   qué cambió y por qué — por ejemplo, por qué el contrato se firmó con un
   apoderado distinto al que propuso ventas.

2. Procedencia por campo. Cada dato relevante carga de qué documento salió, para
   que la nota de procedencia del Formato de Beneficiario Controlador se genere
   sola en lugar de escribirse a mano.

Umbrales vigentes (política Nea, julio 2026):
  - Beneficiario controlador: 25% o más
  - Seis estados de cuenta cuando la línea supera $200,000
  - CSF, comprobante de domicilio: máximo 3 meses de antigüedad
  - Autorización de buró: 3 años
"""

from datetime import date

UMBRAL_BC = 25.0
UMBRAL_ESTADOS_CUENTA = 200000.0
ESTADOS_CUENTA_BASE = 3
ESTADOS_CUENTA_AMPLIADO = 6

TIPOS_CLIENTE = ("persona_moral", "pfae", "persona_fisica")
TIPOS_OBLIGADO = ("persona_moral", "persona_fisica")
CRITERIOS_BC = ("participacion", "control_efectivo")
CONCLUSIONES_ANEXO = ("control_efectivo", "no_identificado", "parcial")


# ─────────────────────────────────────────────────────────────────────────────
# Plantilla del expediente
# ─────────────────────────────────────────────────────────────────────────────
def expediente_vacio():
    """Devuelve la estructura completa con todos los campos en None."""
    return {
        "folio": None,                     # ACRONIMO-NN, asignado en etapa 0
        "grupo": {"acronimo": None, "nombre": None},
        "etapa": "apertura",
        "tipo_cliente": None,              # ver TIPOS_CLIENTE
        "fechas": {"apertura": None, "operacion": None},

        "cliente": {
            "declarado": {"razon_social": None, "giro": None},
            "validado": {
                "razon_social": None, "nombre_comercial": None, "rfc": None,
                "regimen_capital": None, "domicilio_fiscal": None,
                "actividad_economica": None, "regimen_fiscal": None,
                "inicio_operaciones": None, "situacion_contribuyente": None,
                "domicilio": {"calle": None, "num_ext": None, "colonia": None,
                              "cp": None, "municipio": None, "estado": None,
                              "pais": None},
                "telefono": None, "correo": None,
            },
        },

        "constitucion": {
            "instrumento": None, "libro": None, "fecha": None,
            "fedatario": None, "notaria": None, "plaza": None,
            "inscripcion_rpc": None, "cud_economia": None,
            "capital_social": None, "acciones": None, "duracion": None,
            "domicilio_social": None,
        },

        "representante_legal": {
            "propuesto": {"nombre": None, "correo": None, "telefono": None},
            "validado": {
                "nombre": None, "curp": None, "rfc": None, "cargo": None,
                "fecha_nacimiento": None, "pais_nacimiento": None,
                "pais_nacionalidad": None,
                "identificacion": {"tipo": None, "numero": None,
                                   "autoridad_emisora": None, "pais_emisor": None,
                                   "vigencia": None},
                "facultades": {"titulos_credito": None, "individual": None,
                               "limite_monto": None},
                "fundamento": None,
            },
        },
        "cofirmantes": [],                 # solo si el poder es mancomunado

        "beneficiarios_controladores": [],
        "criterio_identificacion": None,   # ver CRITERIOS_BC
        "bc_declaracion": None,            # "conoce" | "no_conoce"
        "estructura_accionaria": [],
        "organo_administracion": {"tipo": None, "presidente": None,
                                  "secretario": None, "comisario": None,
                                  "apoderados": []},
        "analisis_razonado": None,         # dict del anexo, si aplica

        "credito": {
            "solicitada": {"linea": None, "plazo": None, "tarjetas": None,
                           "mensualidad": None},
            "autorizada": {"linea": None, "plazo": None, "mensualidad": None,
                           "fecha": None, "autorizada_por": None,
                           "linea_propuesta_modelo": None},
        },
        "riesgo_pld": {"grado": None, "factores": [], "fecha_evaluacion": None,
                       "evaluado_por": None, "proxima_actualizacion": None},

        "flags": {"domiciliacion": False, "obligado_solidario": False},
        "obligado_solidario": {
            "tipo": None,                  # ver TIPOS_OBLIGADO
            "es_cliente": False, "expediente_ref": None,
            "razon_social": None, "rfc": None, "domicilio": None,
            "rep_legal": None,
            "persona_fisica": {
                "nombre": None, "nacionalidad": None,
                "fecha_lugar_nacimiento": None, "curp": None, "rfc": None,
                "ocupacion": None, "domicilio": None, "telefono": None,
                "correo": None, "estado_civil": None,
                "identificacion": {"tipo": None, "numero": None,
                                   "autoridad_emisora": None},
            },
            "regimen_conyugal": None,
            "conyuge": None,
        },

        "cuentas_bancarias": [],           # {banco, clabe, divisa, titular, periodos[]}
        "documentos": [],                  # {tipo, file_id, fecha_emision, vigente_hasta,
                                           #  legible, superado_por, inscrito}
        "observaciones": [],               # {tipo, descripcion, severidad, estado,
                                           #  aceptada_por, justificacion, fecha}
        "procedencia": {},                 # campo -> documento del que se extrajo
        "cumplimiento": {
            "bc_firmado_por": None, "bc_fecha_firma": None,
            "responsable": None,
        },
        "quien_lleno": None,
    }


def _get(d, ruta, default=None):
    """Acceso por ruta punteada: _get(exp, 'credito.autorizada.linea')"""
    cur = d
    for parte in ruta.split("."):
        if not isinstance(cur, dict) or parte not in cur:
            return default
        cur = cur[parte]
    return cur if cur is not None else default


# ─────────────────────────────────────────────────────────────────────────────
# Compuertas de la etapa 6
# ─────────────────────────────────────────────────────────────────────────────
def compuertas_generacion(exp):
    """Evalúa las condiciones que deben cumplirse antes de generar documentos.

    Devuelve lista de strings; vacía significa que se puede generar.
    """
    fallas = []

    if not _get(exp, "folio"):
        fallas.append("Sin folio asignado (etapa 0).")
    if _get(exp, "tipo_cliente") not in TIPOS_CLIENTE:
        fallas.append("tipo_cliente inválido o ausente: %r" % _get(exp, "tipo_cliente"))

    # ── línea autorizada, no solicitada ─────────────────────────────────────
    linea = _get(exp, "credito.autorizada.linea")
    if not linea:
        fallas.append("Sin línea autorizada. La cotización no es evidencia de línea; "
                      "riesgo debe autorizar o rechazar antes de generar.")

    # ── representante legal validado y apto ─────────────────────────────────
    fac = _get(exp, "representante_legal.validado.facultades", {})
    if not _get(exp, "representante_legal.validado.nombre"):
        fallas.append("Representante legal sin validar (etapa 2).")
    if fac.get("titulos_credito") is not True:
        fallas.append("El representante validado no tiene facultad para suscribir "
                      "títulos de crédito.")
    if fac.get("individual") is not True and not _get(exp, "cofirmantes"):
        fallas.append("El poder es mancomunado y no hay cofirmantes con identificación "
                      "en el expediente.")
    limite = fac.get("limite_monto")
    if linea and limite is not None and float(limite) < float(linea):
        fallas.append("El poder tiene límite de $%s, inferior a la línea autorizada de "
                      "$%s. Se requiere un representante elegible." %
                      (format(float(limite), ",.2f"), format(float(linea), ",.2f")))

    # ── estados de cuenta contra la línea autorizada ────────────────────────
    if linea:
        requeridos = (ESTADOS_CUENTA_AMPLIADO if float(linea) > UMBRAL_ESTADOS_CUENTA
                      else ESTADOS_CUENTA_BASE)
        cuentas = _get(exp, "cuentas_bancarias", [])
        principal = next((c for c in cuentas if c.get("titular_es_cliente")), None)
        n = len(principal.get("periodos", [])) if principal else 0
        if n < requeridos:
            fallas.append("Línea de $%s exige %d estados de cuenta; hay %d." %
                          (format(float(linea), ",.2f"), requeridos, n))

    # ── observaciones ───────────────────────────────────────────────────────
    for o in _get(exp, "observaciones", []):
        if o.get("severidad") == "bloqueante" and o.get("estado") != "resuelta":
            fallas.append("Faltante bloqueante sin resolver: %s" % o.get("descripcion"))
        if (o.get("severidad") == "advertencia" and
                o.get("estado") not in ("resuelta", "aceptada")):
            fallas.append("Observación sin resolver ni aceptar formalmente: %s"
                          % o.get("descripcion"))
        if o.get("estado") == "aceptada" and not o.get("justificacion"):
            fallas.append("Observación aceptada sin justificación escrita: %s"
                          % o.get("descripcion"))

    # ── determinación del beneficiario controlador ──────────────────────────
    if _get(exp, "tipo_cliente") == "persona_moral":
        if not _get(exp, "cumplimiento.bc_firmado_por"):
            fallas.append("La determinación del beneficiario controlador requiere firma "
                          "de cumplimiento en todos los casos.")
        if _get(exp, "criterio_identificacion") not in CRITERIOS_BC:
            fallas.append("criterio_identificacion inválido o ausente.")

    # ── coherencia del obligado solidario ───────────────────────────────────
    if _get(exp, "flags.obligado_solidario"):
        os_ = _get(exp, "obligado_solidario", {})
        if os_.get("tipo") not in TIPOS_OBLIGADO:
            fallas.append("Flag de obligado solidario activo sin tipo definido.")
        if os_.get("es_cliente") and not os_.get("expediente_ref"):
            fallas.append("El obligado solidario es cliente pero no se referenció su "
                          "expediente.")

    # ── domiciliación ───────────────────────────────────────────────────────
    if _get(exp, "flags.domiciliacion"):
        cuentas = _get(exp, "cuentas_bancarias", [])
        if not any(c.get("clabe") for c in cuentas):
            fallas.append("Flag de domiciliación activo sin CLABE en las cuentas "
                          "bancarias del expediente.")

    return fallas


# ─────────────────────────────────────────────────────────────────────────────
# Matriz de documentos
# ─────────────────────────────────────────────────────────────────────────────
def documentos_aplicables(exp):
    """Lista de claves de documento que corresponden a este expediente."""
    tipo = _get(exp, "tipo_cliente")
    docs = ["contrato"]

    if tipo == "persona_moral":
        docs.append("pld_pm")
        if _get(exp, "beneficiarios_controladores"):
            docs.append("beneficiario_controlador")
    else:
        docs.append("pld_pf")

    if _requiere_anexo_razonado(exp):
        docs.append("anexo_razonado")

    if _get(exp, "flags.obligado_solidario"):
        docs.append("adenda_os_pm"
                    if _get(exp, "obligado_solidario.tipo") == "persona_moral"
                    else "adenda_os_pf")

    if _get(exp, "flags.domiciliacion"):
        docs.append("domiciliacion")

    return docs


def _requiere_anexo_razonado(exp):
    """Tres supuestos: control efectivo, sin identificación, o brecha >= 25%."""
    if _get(exp, "tipo_cliente") != "persona_moral":
        return False
    if _get(exp, "criterio_identificacion") == "control_efectivo":
        return True
    if not _get(exp, "beneficiarios_controladores"):
        return True
    total = 0.0
    for a in _get(exp, "estructura_accionaria", []):
        try:
            total += float(a.get("porcentaje") or 0)
        except (TypeError, ValueError):
            return False
    return (100.0 - total) >= UMBRAL_BC


def estados_cuenta_requeridos(exp):
    linea = _get(exp, "credito.autorizada.linea") or _get(exp, "credito.solicitada.linea")
    if not linea:
        return ESTADOS_CUENTA_BASE
    return (ESTADOS_CUENTA_AMPLIADO if float(linea) > UMBRAL_ESTADOS_CUENTA
            else ESTADOS_CUENTA_BASE)
