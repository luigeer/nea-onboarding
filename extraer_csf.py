# -*- coding: utf-8 -*-
"""
extraer_csf.py — Extracción determinista de la Constancia de Situación Fiscal
=============================================================================
La CSF es un PDF generado por el SAT con estructura de tablas fija, así que no
requiere modelo: se leen las celdas y se mapean al schema del expediente.

Rellena unos quince campos del expediente y de paso resuelve tres cosas que
antes se decidían a mano:

  - tipo_cliente, derivado de la longitud del RFC y de los regímenes declarados
  - la razón social completa, que el SAT parte en denominación y régimen de capital
  - la vigencia de la propia CSF contra el límite de tres meses de la etapa 2

Nota sobre la extracción: pdfplumber con la tolerancia por omisión colapsa los
espacios de este PDF ("CONSULTORESRAMSOJ"). Con text_x_tolerance=1.5 se recuperan.

Uso:
    python extraer_csf.py <csf.pdf> [salida.json]
"""

import json
import re
import sys
from datetime import date

import pdfplumber

X_TOL = 1.5

MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
         "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11,
         "DICIEMBRE": 12}

# El SAT guarda la denominación sin el sufijo societario; el sufijo se desprende
# del régimen de capital. Sin esta unión la razón social queda incompleta en el
# contrato y en el formato PLD.
SUFIJOS = [
    ("SOCIEDAD ANONIMA PROMOTORA DE INVERSION DE CAPITAL VARIABLE", "S.A.P.I. de C.V."),
    ("SOCIEDAD ANONIMA PROMOTORA DE INVERSION BURSATIL", "S.A.P.I.B."),
    ("SOCIEDAD ANONIMA PROMOTORA DE INVERSION", "S.A.P.I."),
    ("SOCIEDAD ANONIMA BURSATIL DE CAPITAL VARIABLE", "S.A.B. de C.V."),
    ("SOCIEDAD ANONIMA DE CAPITAL VARIABLE", "S.A. de C.V."),
    ("SOCIEDAD ANONIMA", "S.A."),
    ("SOCIEDAD DE RESPONSABILIDAD LIMITADA DE CAPITAL VARIABLE", "S. de R.L. de C.V."),
    ("SOCIEDAD DE RESPONSABILIDAD LIMITADA", "S. de R.L."),
    ("SOCIEDAD POR ACCIONES SIMPLIFICADA", "S.A.S."),
    ("SOCIEDAD CIVIL", "S.C."),
    ("ASOCIACION CIVIL", "A.C."),
    ("SOCIEDAD EN NOMBRE COLECTIVO", "S. en N.C."),
    ("SOCIEDAD EN COMANDITA SIMPLE", "S. en C.S."),
    ("SOCIEDAD COOPERATIVA DE RESPONSABILIDAD LIMITADA", "S.C. de R.L."),
]

# Entidad de nacimiento según las posiciones 12-13 de la CURP. Con esto la fecha
# y el lugar de nacimiento de beneficiarios y obligados salen de la propia CSF
# en lugar de esperarse a la identificación oficial.
CURP_ESTADOS = {
    "AS": "Aguascalientes", "BC": "Baja California", "BS": "Baja California Sur",
    "CC": "Campeche", "CL": "Coahuila", "CM": "Colima", "CS": "Chiapas",
    "CH": "Chihuahua", "DF": "Ciudad de México", "DG": "Durango",
    "GT": "Guanajuato", "GR": "Guerrero", "HG": "Hidalgo", "JC": "Jalisco",
    "MC": "Estado de México", "MN": "Michoacán", "MS": "Morelos", "NT": "Nayarit",
    "NL": "Nuevo León", "OC": "Oaxaca", "PL": "Puebla", "QT": "Querétaro",
    "QR": "Quintana Roo", "SP": "San Luis Potosí", "SL": "Sinaloa", "SR": "Sonora",
    "TC": "Tabasco", "TS": "Tamaulipas", "TL": "Tlaxcala", "VZ": "Veracruz",
    "YN": "Yucatán", "ZS": "Zacatecas", "NE": "Nacido en el extranjero",
}

RE_CURP = re.compile(r"^[A-Z]{4}(\d{2})(\d{2})(\d{2})[HM]([A-Z]{2})[A-Z]{3}[A-Z0-9]\d$")

RE_FECHA_LARGA = re.compile(r"(\d{1,2})\s*DE\s*([A-ZÁÉÍÓÚÑ]+)\s*DE\s*(\d{4})", re.I)
RE_FECHA_CORTA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
RE_EMISION = re.compile(
    r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]{2,40}?)\s*,\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]{2,30}?)"
    r"\s+A\s+(\d{1,2}\s*DE\s*[A-ZÁÉÍÓÚÑ]+\s*DE\s*\d{4})")


# ─────────────────────────────────────────────────────────────────────────────
def _norm(s):
    if s is None:
        return None
    s = re.sub(r"\s+", " ", str(s).replace("\n", " ")).strip()
    return s or None


def _iso_larga(txt):
    """'03 DE AGOSTO DE 2020' -> '2020-08-03'"""
    if not txt:
        return None
    m = RE_FECHA_LARGA.search(txt)
    if not m:
        return None
    d, mes, a = m.group(1), m.group(2).upper(), m.group(3)
    if mes not in MESES:
        return None
    return "%s-%02d-%02d" % (a, MESES[mes], int(d))


def _iso_corta(txt):
    """'03/08/2020' -> '2020-08-03'"""
    m = RE_FECHA_CORTA.match((txt or "").strip())
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else None


def _mas_meses(iso, meses):
    if not iso:
        return None
    a, m, d = (int(x) for x in iso.split("-"))
    m += meses
    a += (m - 1) // 12
    m = (m - 1) % 12 + 1
    dias = [31, 29 if (a % 4 == 0 and (a % 100 != 0 or a % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return "%04d-%02d-%02d" % (a, m, min(d, dias[m - 1]))


def _sufijo(regimen_capital):
    if not regimen_capital:
        return None, None
    rc = re.sub(r"\s+", " ", regimen_capital.upper()).strip()
    for largo, corto in SUFIJOS:
        if rc.startswith(largo):
            return corto, None
    return None, ("Régimen de capital no reconocido: %r. La razón social se emite sin "
                  "sufijo societario y hay que completarla a mano." % regimen_capital)


# ─────────────────────────────────────────────────────────────────────────────
def _texto_emision(pdf):
    """Lee el cuadro de 'Lugar y Fecha de Emisión'.

    Se recorta la mitad derecha del encabezado porque el texto plano de la página
    entrelaza las dos columnas y parte la fecha: "06 DE JULIO DE social 2026".
    """
    p = pdf.pages[0]
    region = p.crop((p.width * 0.48, 0, p.width, p.height * 0.30))
    return re.sub(r"\s+", " ", region.extract_text(x_tolerance=X_TOL) or "")


def _celdas(pdf):
    """Devuelve (pares etiqueta->valor, tablas crudas, texto completo)."""
    pares, tablas, textos = {}, [], []
    for p in pdf.pages:
        textos.append(p.extract_text(x_tolerance=X_TOL) or "")
        for tb in p.extract_tables(table_settings={"text_x_tolerance": X_TOL}) or []:
            tablas.append(tb)
            for fila in tb:
                celdas = [_norm(c) for c in fila]
                # Primero "Etiqueta: Valor" dentro de una misma celda
                for c in celdas:
                    if c and ":" in c and not c.endswith(":"):
                        et, _, val = c.partition(":")
                        et, val = et.strip(), val.strip()
                        if et and val and len(et) < 60 and et not in pares:
                            pares[et] = val
                # Después "Etiqueta:" | "Valor", solo si el valor no es otra etiqueta
                if (len(celdas) >= 2 and celdas[0] and celdas[0].endswith(":")
                        and celdas[1] and ":" not in celdas[1]):
                    pares.setdefault(celdas[0][:-1].strip(), celdas[1])
    return pares, tablas, "\n".join(textos)


def _actividades(tablas):
    out = []
    for tb in tablas:
        # El encabezado de columnas puede venir en la fila 0 o en la 1, según si la
        # tabla incluye además el título "Actividades Económicas:".
        i_cab = None
        for i, fila in enumerate(tb[:3]):
            if any("Actividad Económica" in (_norm(c) or "") for c in fila):
                i_cab = i
                break
        if i_cab is None:
            continue
        for fila in tb[i_cab + 1:]:
            c = [_norm(x) for x in fila]
            if len(c) < 4 or not c[0] or not str(c[0]).isdigit():
                continue
            try:
                pct = float(c[2])
            except (TypeError, ValueError):
                pct = None
            out.append({"orden": int(c[0]), "actividad": c[1], "porcentaje": pct,
                        "fecha_inicio": _iso_corta(c[3])})
    return out


def _regimenes(tablas):
    out = []
    for tb in tablas:
        cab = [_norm(c) or "" for c in tb[0]] if tb else []
        if not (cab and cab[0] == "Regímenes:"):
            continue
        for fila in tb[1:]:
            c = [_norm(x) for x in fila]
            if not c or not c[0] or c[0] == "Régimen":
                continue
            out.append({"regimen": c[0],
                        "fecha_inicio": _iso_corta(c[1]) if len(c) > 1 else None})
    return out


def _regimen_principal(regimenes, tipo):
    """En PFAE el régimen que rige la operación es el de actividad empresarial,
    no necesariamente el primero que lista la constancia."""
    if not regimenes:
        return None
    if tipo == "pfae":
        for r in regimenes:
            if "Actividades Empresariales" in r["regimen"]:
                return r["regimen"]
    return regimenes[0]["regimen"]


# ─────────────────────────────────────────────────────────────────────────────
def extraer_csf(ruta_pdf):
    """Lee una CSF y devuelve los campos crudos más las alertas de vigencia."""
    with pdfplumber.open(ruta_pdf) as pdf:
        pares, tablas, texto = _celdas(pdf)
        texto_emision = _texto_emision(pdf)

    rfc = _norm(pares.get("RFC"))
    if not rfc:
        raise ValueError("No se encontró el RFC. ¿Es una Constancia de Situación Fiscal?")
    rfc = rfc.replace(" ", "").upper()

    actividades = _actividades(tablas)
    regimenes = _regimenes(tablas)
    alertas = []

    # ── tipo de cliente ─────────────────────────────────────────────────────
    if len(rfc) == 12:
        tipo = "persona_moral"
    elif len(rfc) == 13:
        tipo = ("pfae" if any("Actividades Empresariales" in r["regimen"] for r in regimenes)
                else "persona_fisica")
    else:
        raise ValueError("RFC con %d caracteres, se esperan 12 o 13: %r" % (len(rfc), rfc))

    # ── nombre ──────────────────────────────────────────────────────────────
    nota_sufijo = None
    if tipo == "persona_moral":
        denom = _norm(pares.get("Denominación/Razón Social")) or _norm(
            pares.get("Denominación/RazónSocial"))
        regimen_capital = _norm(pares.get("Régimen Capital")) or _norm(pares.get("RégimenCapital"))
        sufijo, nota_sufijo = _sufijo(regimen_capital)
        razon_social = "%s, %s" % (denom, sufijo) if (denom and sufijo) else denom
        nombre_registral = None
    else:
        nombres = _norm(pares.get("Nombre (s)")) or _norm(pares.get("Nombre(s)"))
        ap1 = _norm(pares.get("Primer Apellido"))
        ap2 = _norm(pares.get("Segundo Apellido"))
        razon_social = " ".join(x for x in [nombres, ap1, ap2] if x)
        nombre_registral = " ".join(x for x in [ap1, ap2, nombres] if x)
        regimen_capital = None
    if nota_sufijo:
        alertas.append(nota_sufijo)

    # ── emisión y vigencia ──────────────────────────────────────────────────
    lugar = fecha_emision = None
    m = RE_EMISION.search(texto_emision)
    if m:
        lugar = "%s, %s" % (_norm(m.group(1)), _norm(m.group(2)))
        fecha_emision = _iso_larga(m.group(3))

    # El cuadro de "Lugar y Fecha de Emisión" cambia de alto según lo largo que
    # sea el nombre del contribuyente, y cuando crece la fecha se sale del
    # recorte y se pierde. La cadena original del sello la trae siempre, en un
    # formato fijo que genera el SAT y no depende de la maquetación:
    #
    #     CadenaOriginalSello: ||2026/08/10 08:05:57|RFC|CONSTANCIA DE ...
    #
    # Se usa como respaldo y, si las dos existen y difieren, gana el sello: es
    # el dato que el propio SAT firmó. Una CSF sin fecha se trata como vencida
    # más adelante, así que perderla no es inofensivo.
    # El espaciado de la etiqueta varía entre constancias —"CadenaOriginalSello"
    # y "Cadena Original Sello"—, así que se ignoran los espacios de la etiqueta.
    sello = re.search(r"Cadena\s*Original\s*Sello:\s*\|\|(\d{4})/(\d{2})/(\d{2})",
                      texto)
    if sello:
        del_sello = "%s-%s-%s" % sello.groups()
        if fecha_emision and fecha_emision != del_sello:
            alertas.append(
                "La fecha del encabezado (%s) no coincide con la del sello digital "
                "(%s); se usa la del sello." % (fecha_emision, del_sello))
        fecha_emision = del_sello
    elif not fecha_emision:
        alertas.append("No se pudo leer la fecha de emisión: hay que verificarla a mano.")
    vigente_hasta = _mas_meses(fecha_emision, 3)
    hoy = date.today().isoformat()
    if vigente_hasta and vigente_hasta < hoy:
        alertas.append("CSF vencida: se emitió el %s y el límite de tres meses se cumplió el %s."
                       % (fecha_emision, vigente_hasta))
    elif vigente_hasta:
        a, mm, d = (int(x) for x in vigente_hasta.split("-"))
        dias = (date(a, mm, d) - date.today()).days
        if dias <= 15:
            alertas.append("CSF vence en %d día(s), el %s." % (dias, vigente_hasta))

    # ── situación del contribuyente ─────────────────────────────────────────
    estatus = _norm(pares.get("Estatus en el padrón")) or _norm(pares.get("Estatusenelpadrón"))
    if estatus and estatus.upper() != "ACTIVO":
        alertas.append("Contribuyente con estatus %r: el expediente no debe abrirse." % estatus)

    # ── actividad principal, por porcentaje y no por orden ──────────────────
    principal = None
    con_pct = [a for a in actividades if a.get("porcentaje") is not None]
    if con_pct:
        principal = max(con_pct, key=lambda a: a["porcentaje"])
    elif actividades:
        principal = actividades[0]

    # ── domicilio ───────────────────────────────────────────────────────────
    g = lambda *ks: next((_norm(pares.get(k)) for k in ks if pares.get(k)), None)
    domicilio = {
        "calle": " ".join(x for x in [g("Tipo de Vialidad", "TipodeVialidad"),
                                      g("Nombre de Vialidad", "NombredeVialidad")] if x) or None,
        "num_ext": g("Número Exterior", "NúmeroExterior"),
        "num_int": g("Número Interior", "NúmeroInterior"),
        "colonia": g("Nombre de la Colonia", "NombredelaColonia"),
        "cp": g("Código Postal", "CódigoPostal"),
        "localidad": g("Nombre de la Localidad", "NombredelaLocalidad"),
        "municipio": g("Nombre del Municipio o Demarcación Territorial"),
        "estado": g("Nombre de la Entidad Federativa", "NombredelaEntidadFederativa"),
        "pais": "México",
        "entre_calle": g("Entre Calle", "EntreCalle"),
        "y_calle": g("Y Calle", "YCalle"),
    }

    return {
        "rfc": rfc, "tipo_cliente": tipo,
        "razon_social": razon_social, "nombre_registral": nombre_registral,
        "curp": (_norm(pares.get("CURP")) or "").replace(" ", "").upper() or None,
        "nombre_comercial": g("Nombre Comercial", "NombreComercial"),
        "regimen_capital": regimen_capital,
        "idcif": (re.search(r"idCIF:\s*(\d+)", texto) or [None, None])[1],
        "fecha_emision": fecha_emision, "lugar_emision": lugar,
        "vigente_hasta": vigente_hasta,
        "inicio_operaciones": _iso_larga(g("Fecha inicio de operaciones",
                                           "Fechainiciodeoperaciones") or ""),
        "situacion_contribuyente": estatus,
        "domicilio": domicilio,
        "actividades": actividades,
        "actividad_principal": principal["actividad"] if principal else None,
        "regimenes": regimenes,
        "regimen_fiscal": _regimen_principal(regimenes, tipo),
        "alertas": alertas,
    }


# ─────────────────────────────────────────────────────────────────────────────
def domicilio_una_linea(dom):
    piezas = [
        " ".join(x for x in [dom.get("calle"), dom.get("num_ext")] if x),
        ("Int. %s" % dom["num_int"]) if dom.get("num_int") else None,
        ("Col. %s" % dom["colonia"]) if dom.get("colonia") else None,
        ("C.P. %s" % dom["cp"]) if dom.get("cp") else None,
        dom.get("municipio"), dom.get("estado"),
    ]
    return ", ".join(p for p in piezas if p)


def _curp_datos(curp):
    """Deriva fecha y entidad de nacimiento de la CURP.

    El dígito 17 distingue el siglo: numérico para nacidos antes de 2000,
    letra a partir de 2000.
    """
    m = RE_CURP.match(curp or "")
    if not m:
        return {}
    aa, mm, dd, ent = m.groups()
    if not (1 <= int(mm) <= 12 and 1 <= int(dd) <= 31):
        return {}
    siglo = "19" if curp[16].isdigit() else "20"
    return {"fecha_nacimiento": "%s/%s/%s%s" % (dd, mm, siglo, aa),
            "lugar_nacimiento": CURP_ESTADOS.get(ent)}


def _tokens_nombre(nombre):
    """Tokens normalizados para comparar nombres sin importar el orden
    (la CSF da 'Nombres Apellidos'; la constitutiva puede traer lo inverso)."""
    if not nombre:
        return None
    limpio = nombre.upper()
    for a, b in zip("ÁÉÍÓÚÜ", "AEIOUU"):
        limpio = limpio.replace(a, b)
    return tuple(sorted(limpio.split()))


def _rellenar(destino, valores):
    """Asigna solo los campos vacíos; lo ya validado no se toca."""
    puestos = []
    for k, v in valores.items():
        if v is not None and destino.get(k) is None:
            destino[k] = v
            puestos.append(k)
    return puestos


def _observar_alertas(csf, exp, tipo):
    for a in csf.get("alertas", []):
        exp["observaciones"].append({
            "tipo": tipo, "descripcion": a, "severidad": "advertencia",
            "estado": "abierta", "fecha": date.today().isoformat(),
        })


def a_obligado_solidario(csf, exp):
    """Vuelca la CSF del obligado solidario en el expediente.

    No toca el flag de obligado solidario: esa decisión es de riesgo (etapa 5).
    Si la CSF llega antes de la decisión, los datos quedan listos y el flag vacío.
    """
    fuente = "CSF del obligado solidario, emitida el %s" % (csf.get("fecha_emision") or "s/d")
    os_ = exp["obligado_solidario"]
    puestos = []

    if csf["rfc"] == (exp["cliente"]["validado"].get("rfc") or ""):
        exp["observaciones"].append({
            "tipo": "csf_obligado",
            "descripcion": "La CSF del obligado solidario trae el mismo RFC que el "
                           "cliente: el cliente no puede garantizarse a sí mismo.",
            "severidad": "bloqueante", "estado": "abierta",
            "fecha": date.today().isoformat(),
        })

    if csf["tipo_cliente"] == "persona_moral":
        os_["tipo"] = os_["tipo"] or "persona_moral"
        puestos += _rellenar(os_, {
            "razon_social": csf["razon_social"],
            "rfc": csf["rfc"],
            "domicilio": domicilio_una_linea(csf["domicilio"]),
        })
    else:
        os_["tipo"] = os_["tipo"] or "persona_fisica"
        pf = os_["persona_fisica"]
        nac = _curp_datos(csf.get("curp"))
        fecha_lugar = None
        if nac.get("fecha_nacimiento") and nac.get("lugar_nacimiento"):
            fecha_lugar = "%s, %s" % (nac["fecha_nacimiento"], nac["lugar_nacimiento"])
        puestos += _rellenar(pf, {
            "nombre": csf["razon_social"],
            "curp": csf.get("curp"),
            "rfc": csf["rfc"],
            "ocupacion": csf.get("actividad_principal"),
            "domicilio": domicilio_una_linea(csf["domicilio"]),
            "fecha_lugar_nacimiento": fecha_lugar,
        })

    exp["documentos"].append({
        "tipo": "csf_obligado_solidario", "fecha_emision": csf.get("fecha_emision"),
        "vigente_hasta": csf.get("vigente_hasta"), "legible": True,
        "idcif": csf.get("idcif"), "superado_por": None,
    })
    for campo in puestos:
        exp["procedencia"]["obligado_solidario.%s" % campo] = fuente
    _observar_alertas(csf, exp, "csf_obligado")
    return puestos


def a_beneficiario(csf, exp):
    """Vuelca la CSF de un beneficiario controlador.

    Si el beneficiario ya existe (lo aportó la lectura de la constitutiva), se
    completan solo sus campos vacíos; la participación y el criterio de
    determinación nunca salen de una CSF. Si no existe, se agrega el registro
    con esos campos pendientes.
    """
    if csf["tipo_cliente"] == "persona_moral":
        raise ValueError(
            "Esta CSF es de una persona moral (%s). El beneficiario controlador es "
            "siempre una persona física; si hay una moral en la cadena de control, "
            "eso se resuelve en la estructura accionaria, no aquí." % csf["razon_social"])

    fuente = "CSF del beneficiario, emitida el %s" % (csf.get("fecha_emision") or "s/d")
    nac = _curp_datos(csf.get("curp"))
    tokens = _tokens_nombre(csf["razon_social"])

    bc = next((b for b in exp["beneficiarios_controladores"]
               if (b.get("rfc") and b["rfc"] == csf["rfc"])
               or (b.get("curp") and csf.get("curp") and b["curp"] == csf["curp"])
               or _tokens_nombre(b.get("nombre")) == tokens), None)
    nuevo = bc is None
    if nuevo:
        bc = {"nombre": None, "fecha_nacimiento": None, "lugar_nacimiento": None,
              "nacionalidad": None, "pais_residencia": None, "curp": None,
              "rfc": None, "ocupacion": None, "domicilio": None,
              "identificacion": {"tipo": None, "dato_nombre": None, "dato": None,
                                 "vigencia": None},
              "participacion": {"porcentaje": None, "monto": None},
              "desglose_acciones": None, "criterio_determinacion": None,
              "forma_participacion": None, "pep": None, "cargo": None, "desde": None}
        exp["beneficiarios_controladores"].append(bc)
        exp["observaciones"].append({
            "tipo": "beneficiario_controlador",
            "descripcion": "Se agregó a %s como beneficiario a partir de su CSF, pero "
                           "su participación y el criterio de determinación deben salir "
                           "de la constitutiva o de la estructura accionaria."
                           % csf["razon_social"],
            "severidad": "advertencia", "estado": "abierta",
            "fecha": date.today().isoformat(),
        })

    puestos = _rellenar(bc, {
        "nombre": csf["razon_social"],
        "curp": csf.get("curp"),
        "rfc": csf["rfc"],
        "ocupacion": csf.get("actividad_principal"),
        "domicilio": domicilio_una_linea(csf["domicilio"]),
        "fecha_nacimiento": nac.get("fecha_nacimiento"),
        "lugar_nacimiento": nac.get("lugar_nacimiento"),
        "pais_residencia": "México" if csf["domicilio"].get("pais") == "México" else None,
    })

    exp["documentos"].append({
        "tipo": "csf_beneficiario", "sujeto": csf["razon_social"],
        "fecha_emision": csf.get("fecha_emision"),
        "vigente_hasta": csf.get("vigente_hasta"), "legible": True,
        "idcif": csf.get("idcif"), "superado_por": None,
    })
    for campo in puestos:
        exp["procedencia"]["beneficiario[%s].%s" % (csf["rfc"], campo)] = fuente
    _observar_alertas(csf, exp, "csf_beneficiario")
    return puestos, nuevo


def a_expediente(csf, exp):
    """Vuelca los campos de la CSF en un expediente del schema.

    No sobreescribe lo ya validado; registra la procedencia de cada campo.
    """
    fuente = "Constancia de Situación Fiscal de %s" % (csf.get("fecha_emision") or "fecha s/d")
    exp["tipo_cliente"] = csf["tipo_cliente"]
    val = exp["cliente"]["validado"]
    val.update({
        "razon_social": csf["razon_social"],
        "nombre_comercial": csf.get("nombre_comercial") or csf["razon_social"],
        "rfc": csf["rfc"],
        "regimen_capital": csf.get("regimen_capital"),
        "actividad_economica": csf.get("actividad_principal"),
        "regimen_fiscal": csf.get("regimen_fiscal"),
        "inicio_operaciones": csf.get("inicio_operaciones"),
        "situacion_contribuyente": csf.get("situacion_contribuyente"),
        "domicilio_fiscal": domicilio_una_linea(csf["domicilio"]),
    })
    d = csf["domicilio"]
    val["domicilio"] = {k: d.get(k) for k in
                        ("calle", "num_ext", "colonia", "cp", "municipio", "estado", "pais")}

    # En persona física la CSF describe al propio cliente, que es también quien firma.
    if csf["tipo_cliente"] != "persona_moral":
        rep = exp["representante_legal"]["validado"]
        rep.setdefault("nombre", csf["razon_social"])
        rep["nombre_registral"] = csf.get("nombre_registral")
        rep["curp"] = csf.get("curp")
        rep["rfc"] = csf["rfc"]

    exp["documentos"].append({
        "tipo": "csf_cliente", "fecha_emision": csf.get("fecha_emision"),
        "vigente_hasta": csf.get("vigente_hasta"), "legible": True,
        "idcif": csf.get("idcif"), "superado_por": None,
    })
    for campo in ("razon_social", "rfc", "regimen_capital", "actividad_economica",
                  "regimen_fiscal", "inicio_operaciones", "domicilio_fiscal"):
        exp["procedencia"][campo] = fuente
    for a in csf.get("alertas", []):
        exp["observaciones"].append({
            "tipo": "csf", "descripcion": a, "severidad": "advertencia",
            "estado": "abierta", "fecha": date.today().isoformat(),
        })
    return exp


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    datos = extraer_csf(sys.argv[1])
    salida = json.dumps(datos, ensure_ascii=False, indent=2)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            fh.write(salida)
        print("Escrito: %s" % sys.argv[2])
    else:
        print(salida)
