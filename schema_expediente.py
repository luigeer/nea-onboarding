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
MOTIVOS_EXCEPCION_RIESGO = ("socio_comercial", "respaldo_obligado_solidario",
                            "prueba_comercial")
# Estatus del padrón con los que el contribuyente opera. REACTIVADO es uno que
# estuvo suspendido y volvió: para el SAT está vivo igual que ACTIVO.
ESTATUS_SAT_OPERANDO = ("ACTIVO", "REACTIVADO")


def estatus_sat_aceptable(estatus):
    return (estatus or "").strip().upper() in ESTATUS_SAT_OPERANDO


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
                "domicilio": {"calle": None, "num_ext": None, "num_int": None,
                              "colonia": None,
                              "cp": None, "municipio": None, "estado": None,
                              "pais": None},
                "telefono": None, "correo": None,
            },
        },

        "constitucion": {
            "instrumento": None, "libro": None, "fecha": None,
            "fedatario": None, "notaria": None, "plaza": None,
            "tipo_fedatario": None,            # "notario" (default) | "corredor"
            "inscripcion_rpc": None, "fecha_inscripcion_rpc": None,
            "cud_economia": None,
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
                # Datos del poder que se imprimen en el Anexo A de Grit.
                "poder": {"escritura": None, "notario": None, "notaria": None},
            },
        },
        "cofirmantes": [],                 # solo si el poder es mancomunado;
                                           # cada entrada lleva nombre y poder
                                           # {escritura, notario, notaria}

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
            # Línea autorizada sin pasar por el modelo de riesgo. Ver
            # `_revisar_excepcion_riesgo`. None = no hay excepción.
            "excepcion_riesgo": None,  # {motivo, justificacion, autorizada_por, fecha}
        },
        "riesgo_pld": {"grado": None, "factores": [], "fecha_evaluacion": None,
                       "evaluado_por": None, "proxima_actualizacion": None},

        # buro_en_paquete: la autorización de buró se firma dentro del paquete
        # en vez de pedirse antes (cuando no hace falta consultar buró previo).
        "flags": {"domiciliacion": False, "obligado_solidario": False,
                  "buro_en_paquete": False},
        # Garante persona física que acompaña —no sustituye— al corporativo.
        # Ver el comentario en `documentos_aplicables`.
        "obligado_solidario_pf": {
            "nombre": None, "nacionalidad": None, "fecha_lugar_nacimiento": None,
            "curp": None, "rfc": None, "ocupacion": None, "domicilio": None,
            "telefono": None, "correo": None, "estado_civil": None,
            "regimen_conyugal": None, "conyuge": None,
            "identificacion": {"tipo": None, "numero": None,
                               "autoridad_emisora": None},
            "motivo": None,     # por qué se pidió además de la garantía corporativa
            # Cuando se decide no pedir la garantía personal, esto queda con el
            # motivo, la fecha y quién decidió; el resto del bloque se conserva
            # como historia. Ver `documentos_aplicables`.
            "no_aplica": None,
        },
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

        # El cliente firma solo con Grit Payment. Ver `documentos_aplicables`.
        "sin_grit_mobility": None,         # {justificacion, decidido_por, fecha}

        # Condiciones comerciales del Contrato de Prestación de Servicios de
        # Grit Mobility (monedero de combustible). No son datos KYC, salen de
        # la propuesta comercial ya negociada con el cliente.
        "grit_monedero": {
            "modelo_negocio": None,     # "prepago" | "postpago"
            "comision": None,           # % sobre monto depositado
            "cuota": None,              # anual o mensual, texto libre
            "costo_tarjeta": None,
            "comentarios": None,
            "contacto": {"nombre": None, "telefono_1": None, "telefono_2": None,
                        "correo": None},
            # Si es None/vacío, el generador reutiliza cliente.validado.domicilio.
            "domicilio_entrega": {"calle": None, "num_ext": None, "num_int": None,
                                  "colonia": None, "cp": None, "municipio": None,
                                  "estado": None},
        },
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
def compuertas_grit(exp):
    """Datos del Anexo A que no pueden sustituirse por guiones ni fechas ajenas."""
    fallas = []
    gm = _get(exp, "grit_monedero", {}) or {}

    def informado(valor):
        return valor is not None and (not isinstance(valor, str) or bool(valor.strip()))

    if gm.get("modelo_negocio") not in ("prepago", "postpago"):
        fallas.append("Grit: falta grit_monedero.modelo_negocio (prepago o postpago).")
    for campo in ("comision", "cuota", "costo_tarjeta"):
        valor = gm.get(campo)
        if not informado(valor):
            fallas.append("Grit: falta grit_monedero.%s; indica el valor o 'No aplica'."
                          % campo)

    if _get(exp, "tipo_cliente") == "persona_moral":
        if not informado(_get(exp, "constitucion.inscripcion_rpc")):
            fallas.append("Grit: falta constitucion.inscripcion_rpc para el Anexo A.")
        fecha_rpc = _get(exp, "constitucion.fecha_inscripcion_rpc")
        try:
            date.fromisoformat(fecha_rpc)
        except (TypeError, ValueError):
            fallas.append("Grit: falta constitucion.fecha_inscripcion_rpc válida "
                          "(AAAA-MM-DD) para el Anexo A.")

        representantes = [(_get(exp, "representante_legal.validado", {}) or {},
                           "representante_legal.validado")]
        representantes.extend((co, "cofirmantes[%d]" % i)
                              for i, co in enumerate(_get(exp, "cofirmantes", []) or []))
        for rep, ruta in representantes:
            poder = rep.get("poder") or {}
            for campo in ("escritura", "notario", "notaria"):
                if not informado(poder.get(campo)):
                    fallas.append("Grit: falta %s.poder.%s para el Anexo A."
                                  % (ruta, campo))
    return fallas


def _informado(valor):
    return valor is not None and (not isinstance(valor, str) or bool(valor.strip()))


def _revisar_excepcion_riesgo(exp):
    """(vigente, fallas) de la excepción al modelo de riesgo.

    Hay líneas que se autorizan sin modelo: un socio comercial al que por
    decisión de dirección no se le pide información financiera, o un cliente
    respaldado por un obligado solidario que ya tiene autorizada una línea
    mayor. La excepción exime de los estados de cuenta y de nada más —el KYC,
    la línea autorizada y las facultades del representante se siguen
    exigiendo—, y solo cuenta si dice por qué y quién respondió por ella. Una
    excepción a medio llenar no exime: se reporta.
    """
    exc = _get(exp, "credito.excepcion_riesgo")
    if not exc:
        return False, []
    fallas = []
    if exc.get("motivo") not in MOTIVOS_EXCEPCION_RIESGO:
        fallas.append("Excepción de riesgo con motivo inválido: %r (válidos: %s)."
                      % (exc.get("motivo"), ", ".join(MOTIVOS_EXCEPCION_RIESGO)))
    if not _informado(exc.get("justificacion")):
        fallas.append("Excepción de riesgo sin justificación escrita.")
    if not _informado(exc.get("autorizada_por")):
        fallas.append("Excepción de riesgo sin nombre de quién la autoriza.")
    if (exc.get("motivo") == "respaldo_obligado_solidario"
            and not _get(exp, "flags.obligado_solidario")):
        fallas.append("Excepción por respaldo de obligado solidario, pero el "
                      "expediente no tiene obligado solidario.")
    return not fallas, fallas


def excepcion_riesgo_vigente(exp):
    """True si hay una excepción al modelo de riesgo completa y válida."""
    return _revisar_excepcion_riesgo(exp)[0]


def _revisar_sin_grit_mobility(exp):
    """(vigente, fallas) de la exclusión de los documentos de Grit Mobility."""
    sg = _get(exp, "sin_grit_mobility")
    if not sg:
        return False, []
    fallas = []
    if not _informado(sg.get("justificacion")):
        fallas.append("Exclusión de Grit Mobility sin justificación escrita.")
    if not _informado(sg.get("decidido_por")):
        fallas.append("Exclusión de Grit Mobility sin nombre de quién la decidió.")
    return not fallas, fallas


def _revisar_solo_grit_mobility(exp):
    """(vigente, fallas) del paquete que lleva únicamente Grit Mobility.

    Es el espejo de `sin_grit_mobility`: un cliente que solo contrata el
    monedero de combustible, sin línea de crédito de Nea. Cuenta solo con
    justificación escrita y nombre de quien lo decidió.
    """
    sg = _get(exp, "solo_grit_mobility")
    if not sg:
        return False, []
    fallas = []
    if not _informado(sg.get("justificacion")):
        fallas.append("Paquete de solo Grit Mobility sin justificación escrita.")
    if not _informado(sg.get("decidido_por")):
        fallas.append("Paquete de solo Grit Mobility sin nombre de quién lo decidió.")
    return not fallas, fallas


def solo_grit_mobility_vigente(exp):
    """True si el cliente solo firma Grit Mobility, con la decisión completa."""
    return _revisar_solo_grit_mobility(exp)[0]


def compuertas_generacion(exp):
    """Evalúa las condiciones que deben cumplirse antes de generar documentos.

    Devuelve lista de strings; vacía significa que se puede generar.
    """
    fallas = []

    if not _get(exp, "folio"):
        fallas.append("Sin folio asignado (etapa 0).")
    if _get(exp, "tipo_cliente") not in TIPOS_CLIENTE:
        fallas.append("tipo_cliente inválido o ausente: %r" % _get(exp, "tipo_cliente"))
    else:
        sin_grit, fallas_sg = _revisar_sin_grit_mobility(exp)
        fallas.extend(fallas_sg)
        if not sin_grit:
            fallas.extend(compuertas_grit(exp))

    solo_grit, fallas_solo = _revisar_solo_grit_mobility(exp)
    fallas.extend(fallas_solo)
    if _get(exp, "solo_grit_mobility") and _get(exp, "sin_grit_mobility"):
        fallas.append("El expediente dice a la vez solo Grit Mobility y sin Grit "
                      "Mobility: es una contradicción, hay que quitar una de las dos.")

    excepcion, fallas_exc = _revisar_excepcion_riesgo(exp)
    fallas.extend(fallas_exc)

    # ── línea autorizada, no solicitada ─────────────────────────────────────
    # Solo Grit Mobility no tiene crédito: no hay línea, ni estados de cuenta
    # contra ella, ni pagarés que el representante tenga que poder suscribir.
    linea = None if solo_grit else _get(exp, "credito.autorizada.linea")
    if not linea and not solo_grit:
        fallas.append("Sin línea autorizada. La cotización no es evidencia de línea; "
                      "riesgo debe autorizar o rechazar antes de generar.")

    # ── representante legal validado y apto ─────────────────────────────────
    # Persona moral: hay poderes que leer del acta constitutiva. Un PFAE firma
    # por su propio derecho, así que en vez de facultades se exige que su
    # propia identidad esté completa (los mismos datos que pide el Anexo 3).
    if _get(exp, "tipo_cliente") == "persona_moral":
        fac = _get(exp, "representante_legal.validado.facultades", {})
        if not _get(exp, "representante_legal.validado.nombre"):
            fallas.append("Representante legal sin validar (etapa 2).")
        if fac.get("titulos_credito") is not True and not solo_grit:
            fallas.append("El representante validado no tiene facultad para suscribir "
                          "títulos de crédito.")
        if (fac.get("individual") is not True and not _get(exp, "cofirmantes")
                and not solo_grit):
            fallas.append("El poder es mancomunado y no hay cofirmantes con "
                          "identificación en el expediente.")
        limite = fac.get("limite_monto")
        if linea and limite is not None and float(limite) < float(linea):
            fallas.append("El poder tiene límite de $%s, inferior a la línea "
                          "autorizada de $%s. Se requiere un representante elegible." %
                          (format(float(limite), ",.2f"), format(float(linea), ",.2f")))
    else:
        val = _get(exp, "representante_legal.validado", {}) or {}
        ident = val.get("identificacion") or {}
        if not val.get("nombre"):
            fallas.append("Representante legal sin validar (etapa 2).")
        else:
            campos = (
                ("CURP", val.get("curp")), ("RFC", val.get("rfc")),
                ("fecha de nacimiento", val.get("fecha_nacimiento")),
                ("país de nacimiento", val.get("pais_nacimiento")),
                ("país de nacionalidad", val.get("pais_nacionalidad")),
                ("tipo de identificación", ident.get("tipo")),
                ("número de identificación", ident.get("numero")),
                ("autoridad emisora", ident.get("autoridad_emisora")),
                ("país emisor", ident.get("pais_emisor")),
            )
            faltantes = [nombre for nombre, valor in campos if not valor]
            if faltantes:
                fallas.append("Identidad del cliente (PFAE) incompleta: falta %s." %
                              ", ".join(faltantes))

    # ── estados de cuenta contra la línea autorizada ────────────────────────
    if linea and not excepcion:
        requeridos =(ESTADOS_CUENTA_AMPLIADO if float(linea) > UMBRAL_ESTADOS_CUENTA
                      else ESTADOS_CUENTA_BASE)
        cuentas = _get(exp, "cuentas_bancarias", [])
        principal = next((c for c in cuentas if c.get("titular_es_cliente")), None)
        n = len(principal.get("periodos", [])) if principal else 0
        if n < requeridos:
            fallas.append("Línea de $%s exige %d estados de cuenta; hay %d." %
                          (format(float(linea), ",.2f"), requeridos, n))

    # ── observaciones ───────────────────────────────────────────────────────
    # Tres niveles. Una gravedad alta significa que el documento existe pero no
    # sirve —una identificación vencida, un contribuyente que no está ACTIVO—,
    # y eso no se acepta con justificación: se reemplaza. Una intermedia sí
    # puede aceptarla cumplimiento, pero nunca sin justificación escrita.
    # 'bloqueante' y 'advertencia' son los nombres viejos de alta e intermedia.
    ALTAS = ("alta", "bloqueante")
    INTERMEDIAS = ("intermedia", "advertencia")

    # Hay dos clases de observación y la distinción importa aquí:
    #
    #   documento  el papel existe y no sirve. Una identificación vencida no se
    #              justifica: se reemplaza. Es el caso que esta compuerta fue
    #              escrita para atajar.
    #   riesgo     un hecho del negocio que la revisión encontró —que todos los
    #              depósitos vengan del garante, que la cuenta entregada no sea
    #              la operativa—. No hay documento que reemplazar: eso lo resuelve
    #              una decisión de crédito, y la decisión se toma sabiéndolo.
    #
    # La clase también dice QUIÉN firma la aceptación, y no es lo mismo: una
    # observación de clase `documento` —aceptar un comprobante de domicilio que
    # no cumple la política de tres meses— la acepta quien responde por la
    # política, o sea cumplimiento. Una de clase `riesgo` la asume quien decide
    # el crédito. Confundirlas pone la firma equivocada en un registro que existe
    # justamente para saber quién respondió por qué.
    #
    # Sin esta distinción un hallazgo de riesgo grave bloqueaba la generación sin
    # salida posible, y la única forma de avanzar era bajarle la gravedad, que es
    # justo lo que no se quiere que alguien haga. Un riesgo alto sí se puede
    # aceptar, pero exige justificación escrita Y nombre de quien la firma.
    for o in _get(exp, "observaciones", []):
        sev, estado = o.get("severidad"), o.get("estado")
        es_riesgo = o.get("clase") == "riesgo"
        if sev in ALTAS and estado != "resuelta":
            if es_riesgo and estado == "aceptada":
                if not o.get("aceptada_por"):
                    fallas.append("Riesgo alto aceptado sin nombre de quien lo asume: %s"
                                  % o.get("descripcion"))
            else:
                fallas.append("Observación de gravedad alta sin resolver: %s"
                              % o.get("descripcion"))
        if sev in INTERMEDIAS and estado not in ("resuelta", "aceptada"):
            fallas.append("Observación sin resolver ni aceptar formalmente: %s"
                          % o.get("descripcion"))
        if estado == "aceptada" and not o.get("justificacion"):
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

    # Solo Grit Mobility: el monedero sin crédito. Sin carátula, PLD ni BC de
    # Grit Payment, y sin nada que cuelgue del crédito (adenda de obligado
    # solidario, buró, domiciliación). Tampoco el anexo razonado, que va
    # dirigido a Grit Payment; el BC de Grit Mobility ya lleva la determinación.
    if solo_grit_mobility_vigente(exp):
        if tipo == "persona_moral":
            docs = ["grit_contrato", "grit_pld_pm"]
            if _get(exp, "beneficiarios_controladores"):
                docs.append("grit_beneficiario_controlador")
            return docs
        return ["grit_contrato", "grit_pld_pf"]
    docs = ["contrato" if tipo == "persona_moral" else "contrato_pfae"]

    # A partir de septiembre 2026, todo cliente firma también su PLD, su
    # Beneficiario Controlador (si aplica) y su Contrato de Prestación de
    # Servicios a nombre de Grit Mobility, S.A. de C.V. — los use o no. Son el
    # mismo expediente KYC, solo dirigidos a un sujeto obligado distinto, así
    # que siguen uno a uno a su equivalente de Nea.
    #
    # La excepción es `sin_grit_mobility`: un cliente que solo firma con Grit
    # Payment. Cuenta solo si dice por qué y quién lo decidió; a medio llenar
    # los documentos siguen saliendo y la compuerta lo reporta.
    grit, _ = _revisar_sin_grit_mobility(exp)
    grit = not grit
    if grit:
        docs.append("grit_contrato")
    if tipo == "persona_moral":
        docs.append("pld_pm")
        if grit:
            docs.append("grit_pld_pm")
        if _get(exp, "beneficiarios_controladores"):
            docs.append("beneficiario_controlador")
            if grit:
                docs.append("grit_beneficiario_controlador")
    else:
        docs.append("pld_pf")
        if grit:
            docs.append("grit_pld_pf")

    if _requiere_anexo_razonado(exp):
        docs.append("anexo_razonado")

    if _get(exp, "flags.obligado_solidario"):
        docs.append("adenda_os_pm"
                    if _get(exp, "obligado_solidario.tipo") == "persona_moral"
                    else "adenda_os_pf")

    # Una garantía corporativa y una personal pueden coexistir, y a veces deben.
    # El caso que lo motivó: la escritura del garante lo faculta a "obligar
    # cambiariamente a la sociedad" pero no dice "solidariamente", así que la
    # exigibilidad de la adenda corporativa queda en duda. La solución no fue
    # bajarle la gravedad a la observación: fue que el accionista de control
    # firmara además por su propio derecho, de modo que si la corporativa falla
    # quede la personal.
    #
    # `no_aplica` es la salida de ese caso cuando se decide **no** pedir la
    # garantía personal. El bloque no se borra: se marca. Borrarlo dejaría el
    # expediente sin memoria de que se pidió y se descartó, y el que lo lea el
    # año que viene no sabría si fue una decisión o un olvido. Marcarlo evita
    # además lo peor: que el siguiente `generar` vuelva a producir un documento
    # que alguien ya decidió que no va.
    if (_get(exp, "obligado_solidario_pf.nombre")
            and not _get(exp, "obligado_solidario_pf.no_aplica")):
        if "adenda_os_pf" not in docs:
            docs.append("adenda_os_pf")

    if _get(exp, "flags.domiciliacion"):
        docs.append("domiciliacion")

    if _get(exp, "flags.buro_en_paquete"):
        docs.append("autorizacion_buro")

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
