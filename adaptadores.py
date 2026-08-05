# -*- coding: utf-8 -*-
"""
adaptadores.py — Traducción del schema canónico al diccionario de cada generador
================================================================================
Los ocho generadores se escribieron en momentos distintos y cada uno espera una
forma distinta de diccionario: generar_contrato quiere el nombre del representante
en orden apellidos-nombre, generar_adenda_pf quiere anidamiento bajo "obligado",
generar_beneficiario quiere cliente.instrumento.numero. El schema es uno solo.

Esta capa es el único lugar donde vive esa traducción. Si algún generador cambia
su contrato de entrada, se ajusta aquí y no en el orquestador.

Cada función recibe el expediente completo y devuelve el dict del generador.
"""

from schema_expediente import _get

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de formato
# ─────────────────────────────────────────────────────────────────────────────
def _moneda(v):
    if v in (None, ""):
        return None
    return "$%s M.N." % format(float(v), ",.2f")


def _fecha_larga(iso):
    """'2026-07-29' -> '29 de julio de 2026'. Devuelve el valor tal cual si no parsea."""
    if not iso:
        return None
    try:
        a, m, d = str(iso).split("-")
        return "%d de %s de %s" % (int(d), MESES[int(m) - 1], a)
    except (ValueError, IndexError):
        return iso


def _fecha_corta(iso):
    """'2026-07-29' -> '29/07/2026'."""
    if not iso:
        return None
    try:
        a, m, d = str(iso).split("-")
        return "%s/%s/%s" % (d, m, a)
    except ValueError:
        return iso


def _apellidos_primero(nombre):
    """'Juan Alberto Pérez García' -> 'PEREZ GARCIA JUAN ALBERTO'.

    El generador del contrato espera ese orden. Heurística: los dos últimos
    tokens son los apellidos. Si el nombre ya viene en orden registral desde el
    schema, conviene guardarlo en representante_legal.validado.nombre_registral
    y esta función no se usa.
    """
    if not nombre:
        return None
    partes = nombre.split()
    if len(partes) < 3:
        return nombre.upper()
    return " ".join(partes[-2:] + partes[:-2]).upper()


def _domicilio_una_linea(dom):
    if not dom:
        return None
    piezas = [
        " ".join(x for x in [dom.get("calle"), dom.get("num_ext")] if x),
        ("Col. %s" % dom["colonia"]) if dom.get("colonia") else None,
        ("C.P. %s" % dom["cp"]) if dom.get("cp") else None,
        dom.get("municipio"), dom.get("estado"),
    ]
    return ", ".join(p for p in piezas if p)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Contrato de crédito
# ─────────────────────────────────────────────────────────────────────────────
def para_contrato(exp):
    val = _get(exp, "cliente.validado", {})
    rep = _get(exp, "representante_legal.validado", {})
    aut = _get(exp, "credito.autorizada", {})
    razon = val.get("razon_social")
    return {
        "razon_social": (razon or "").upper(),
        "nombre_comercial": (val.get("nombre_comercial") or razon or "").upper(),
        "rep_legal": rep.get("nombre_registral") or _apellidos_primero(rep.get("nombre")),
        "rfc_empresa": val.get("rfc"),
        "linea_credito": _moneda(aut.get("linea")),
        "mensualidad": _moneda(aut.get("mensualidad")),
        "firma_razon_social": (razon or "").upper(),
        "firma_rep_legal": (rep.get("nombre") or "").upper(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Expediente PLD — Anexo 4, persona moral
# ─────────────────────────────────────────────────────────────────────────────
def para_pld_pm(exp):
    val = _get(exp, "cliente.validado", {})
    dom = val.get("domicilio", {}) or {}
    rep = _get(exp, "representante_legal.validado", {})
    ident = rep.get("identificacion", {}) or {}
    benes = _get(exp, "beneficiarios_controladores", [])
    return {
        "fecha_operacion": _fecha_corta(_get(exp, "fechas.operacion")),
        "razon_social": val.get("razon_social"),
        "fecha_constitucion": _fecha_corta(_get(exp, "constitucion.fecha")),
        "pais_nacionalidad": "México",
        "rfc_empresa": val.get("rfc"),
        "actividad_giro": val.get("actividad_economica"),
        "calle": dom.get("calle"), "num_ext": dom.get("num_ext"),
        "colonia": dom.get("colonia"), "cp": dom.get("cp"),
        "municipio": dom.get("municipio"), "estado": dom.get("estado"),
        "pais_domicilio": dom.get("pais") or "México",
        "telefono": val.get("telefono"), "correo": val.get("correo"),
        "nombre_rep": rep.get("nombre_registral") or _apellidos_primero(rep.get("nombre")),
        "fecha_nac_rep": _fecha_corta(rep.get("fecha_nacimiento")),
        "pais_nac_rep": rep.get("pais_nacimiento") or "México",
        "pais_nacionalidad_rep": rep.get("pais_nacionalidad") or "México",
        "curp_rep": rep.get("curp"), "rfc_rep": rep.get("rfc"),
        "tipo_id": ident.get("tipo"), "num_id": ident.get("numero"),
        "autoridad_emisora": ident.get("autoridad_emisora"),
        "pais_emisor": ident.get("pais_emisor") or "México",
        "quien_lleno": exp.get("quien_lleno"),
        "firma_razon_social": val.get("razon_social"),
        "firma_rep_legal": (rep.get("nombre") or "").upper(),
        "cargo_rep": rep.get("cargo") or "Representante Legal",
        # Declaración sobre beneficiario controlador
        "bc_declaracion": _get(exp, "bc_declaracion") or "no_conoce",
        "bc_cantidad": len(benes) or None,
        "tipo_persona": "moral",
        "constancia_obtenida": True,
        # Casillas de documentación
        "comprobante_tipo": _doc_attr(exp, "comprobante_domicilio", "subtipo", "luz"),
        "poder_tipo": _doc_attr(exp, "poder", "subtipo", "testimonio"),
        "tipo_id_oficial": _id_oficial(ident.get("tipo")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Expediente PLD — Anexo 3, persona física / PFAE
# ─────────────────────────────────────────────────────────────────────────────
def para_pld_pf(exp):
    val = _get(exp, "cliente.validado", {})
    dom = val.get("domicilio", {}) or {}
    rep = _get(exp, "representante_legal.validado", {})
    ident = rep.get("identificacion", {}) or {}
    benes = _get(exp, "beneficiarios_controladores", [])
    return {
        "fecha_operacion": _fecha_corta(_get(exp, "fechas.operacion")),
        "nombre_completo": rep.get("nombre_registral") or _apellidos_primero(rep.get("nombre")),
        "fecha_nacimiento": _fecha_corta(rep.get("fecha_nacimiento")),
        "pais_nacimiento": rep.get("pais_nacimiento") or "México",
        "pais_nacionalidad": rep.get("pais_nacionalidad") or "México",
        "curp": rep.get("curp"), "rfc": rep.get("rfc") or val.get("rfc"),
        "actividad_ocupacion": val.get("actividad_economica"),
        "calle": dom.get("calle"), "num_ext": dom.get("num_ext"),
        "colonia": dom.get("colonia"), "cp": dom.get("cp"),
        "municipio": dom.get("municipio"), "estado": dom.get("estado"),
        "pais_domicilio": dom.get("pais") or "México",
        "telefono": val.get("telefono"), "correo": val.get("correo"),
        "tipo_id": ident.get("tipo"), "num_id": ident.get("numero"),
        "autoridad_emisora": ident.get("autoridad_emisora"),
        "pais_emisor": ident.get("pais_emisor") or "México",
        "quien_lleno": exp.get("quien_lleno"),
        "tipo_id_oficial": _id_oficial(ident.get("tipo")),
        "constancia_curp": True,
        "comprobante_tipo": _doc_attr(exp, "comprobante_domicilio", "subtipo", "luz"),
        "constancia_obtenida": True,
        "bc_declaracion": _get(exp, "bc_declaracion") or "no_conoce",
        "bc_cantidad": len(benes) or None,
        "actua_como_apoderado": bool(_get(exp, "actua_como_apoderado")),
        "carta_poder_obtenida": bool(_get(exp, "carta_poder_obtenida")),
        "consiente_transferencia": True,
        "firma_nombre": (rep.get("nombre") or "").upper(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Formato de identificación del beneficiario controlador
# ─────────────────────────────────────────────────────────────────────────────
def para_beneficiario(exp):
    val = _get(exp, "cliente.validado", {})
    con = _get(exp, "constitucion", {})
    rep = _get(exp, "representante_legal.validado", {})
    return {
        "folio": exp.get("folio"),
        "fecha_llenado": _fecha_corta(_get(exp, "fechas.operacion")),
        "criterio_identificacion": _get(exp, "criterio_identificacion") or "participacion",
        "cliente": {
            "razon_social": val.get("razon_social"),
            "rfc": val.get("rfc"),
            "fecha_constitucion": _fecha_corta(con.get("fecha")),
            "instrumento": {"numero": con.get("instrumento"), "libro": con.get("libro"),
                            "fecha": _fecha_corta(con.get("fecha"))},
            "fedatario": {"nombre": con.get("fedatario"), "numero": con.get("notaria"),
                          "plaza": con.get("plaza")},
            "cud_economia": con.get("cud_economia"),
            "domicilio_fiscal": val.get("domicilio_fiscal") or _domicilio_una_linea(
                val.get("domicilio")),
            "domicilio_social": con.get("domicilio_social"),
            "duracion": con.get("duracion"),
            "actividad_economica": val.get("actividad_economica"),
            "regimen_fiscal": val.get("regimen_fiscal"),
            "inicio_operaciones": _fecha_corta(val.get("inicio_operaciones")),
            "capital_social": con.get("capital_social"),
            "acciones": con.get("acciones"),
        },
        "beneficiarios": _get(exp, "beneficiarios_controladores", []),
        "estructura_accionaria": _get(exp, "estructura_accionaria", []),
        "organo_administracion": _get(exp, "organo_administracion", {}),
        "firmante_cliente": {"nombre": rep.get("nombre"),
                             "cargo": rep.get("cargo") or "Representante Legal"},
        "responsable_cumplimiento": _get(exp, "cumplimiento.responsable") or {},
        "procedencia": sorted(set(exp.get("procedencia", {}).values())),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Anexo de análisis razonado
# ─────────────────────────────────────────────────────────────────────────────
def para_anexo_razonado(exp):
    val = _get(exp, "cliente.validado", {})
    base = dict(_get(exp, "analisis_razonado") or {})
    base.setdefault("folio", exp.get("folio"))
    base.setdefault("fecha", _fecha_larga(_get(exp, "fechas.operacion")))
    base.setdefault("lugar", "Ciudad de México")
    base.setdefault("cliente", {})
    base["cliente"].setdefault("razon_social", val.get("razon_social"))
    base["cliente"].setdefault("rfc", val.get("rfc"))
    base["cliente"].setdefault("fecha_operacion", _fecha_corta(_get(exp, "fechas.operacion")))
    base.setdefault("responsable", _get(exp, "cumplimiento.responsable") or {})
    if not base.get("analisis_participacion"):
        base["analisis_participacion"] = {
            "tabla": [{"accionista": a.get("accionista"),
                       "naturaleza": a.get("naturaleza", "Persona física"),
                       "porcentaje": a.get("porcentaje")}
                      for a in _get(exp, "estructura_accionaria", [])]
        }
    return base


# ─────────────────────────────────────────────────────────────────────────────
# 6. Adenda de obligado solidario — persona moral
# ─────────────────────────────────────────────────────────────────────────────
def para_adenda_pm(exp):
    os_ = _get(exp, "obligado_solidario", {})
    return {
        "fecha": _fecha_larga(_get(exp, "fechas.operacion")),
        "cliente_razon_social": _get(exp, "cliente.validado.razon_social"),
        "cliente_rep_legal": _get(exp, "representante_legal.validado.nombre"),
        "obligado_razon_social": os_.get("razon_social"),
        "obligado_rep_legal": os_.get("rep_legal"),
        "obligado_rfc": os_.get("rfc"),
        "obligado_domicilio": os_.get("domicilio"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. Adenda de obligado solidario — persona física
# ─────────────────────────────────────────────────────────────────────────────
def para_adenda_pf(exp):
    os_ = _get(exp, "obligado_solidario", {})
    pf = dict(os_.get("persona_fisica") or {})
    ident = pf.pop("identificacion", {}) or {}
    obligado = {
        "nombre": pf.get("nombre"),
        "nacionalidad": pf.get("nacionalidad") or "Mexicana",
        "fecha_lugar_nacimiento": pf.get("fecha_lugar_nacimiento"),
        "curp": pf.get("curp"), "rfc": pf.get("rfc"),
        "ocupacion": pf.get("ocupacion"),
        "id_tipo": ident.get("tipo"), "id_numero": ident.get("numero"),
        "id_autoridad": ident.get("autoridad_emisora"),
        "domicilio": pf.get("domicilio"),
        "telefono": pf.get("telefono"), "correo": pf.get("correo"),
    }
    if pf.get("estado_civil"):
        obligado["estado_civil"] = pf["estado_civil"]
    d = {
        "fecha": _fecha_larga(_get(exp, "fechas.operacion")),
        "cliente_razon_social": _get(exp, "cliente.validado.razon_social"),
        "cliente_rep_legal": _get(exp, "representante_legal.validado.nombre"),
        "obligado": obligado,
    }
    if os_.get("regimen_conyugal"):
        d["regimen_conyugal"] = os_["regimen_conyugal"]
    if os_.get("conyuge"):
        d["conyuge"] = os_["conyuge"]
    return d


# ─────────────────────────────────────────────────────────────────────────────
# 8. Autorización de domiciliación
# ─────────────────────────────────────────────────────────────────────────────
def para_domiciliacion(exp):
    cuentas = _get(exp, "cuentas_bancarias", [])
    cta = next((c for c in cuentas if c.get("clabe") and c.get("divisa", "MXN") == "MXN"), None)
    cta = cta or (cuentas[0] if cuentas else {})
    return {
        "razon_social": _get(exp, "cliente.validado.razon_social"),
        "representante": _get(exp, "representante_legal.validado.nombre"),
        "banco": cta.get("banco"),
        "clabe": cta.get("clabe"),
        "fecha": _fecha_larga(_get(exp, "fechas.operacion")),
        "periodicidad": "Mensual",
        "opcion_cargo": _get(exp, "domiciliacion_opcion_cargo") or "saldo_total",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de documentos
# ─────────────────────────────────────────────────────────────────────────────
def _doc_attr(exp, tipo, attr, default=None):
    for d in _get(exp, "documentos", []):
        if d.get("tipo") == tipo and not d.get("superado_por"):
            return d.get(attr) or default
    return default


_MAPA_ID = {
    "credencial para votar": "ife", "ine": "ife", "ife": "ife",
    "pasaporte": "pasaporte", "cédula profesional": "cedula",
    "cedula profesional": "cedula", "licencia": "licencia",
    "documento migratorio": "migratorio",
}


def _id_oficial(tipo_texto):
    """Normaliza el texto de la identificación a la clave de casilla del formato."""
    if not tipo_texto:
        return "ife"
    t = tipo_texto.lower()
    for clave, valor in _MAPA_ID.items():
        if clave in t:
            return valor
    return "ife"


ADAPTADORES = {
    "contrato": para_contrato,
    "pld_pm": para_pld_pm,
    "pld_pf": para_pld_pf,
    "beneficiario_controlador": para_beneficiario,
    "anexo_razonado": para_anexo_razonado,
    "adenda_os_pm": para_adenda_pm,
    "adenda_os_pf": para_adenda_pf,
    "domiciliacion": para_domiciliacion,
}
