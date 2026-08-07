# -*- coding: utf-8 -*-
"""
validador.py — Revisión del expediente y solicitud de faltantes
================================================================
Dos preguntas distintas, en orden:

  etapa 1   ¿están todos los documentos?
  etapa 2   ¿sirven? — vigencias, coherencia entre documentos, y sobre todo si
            el representante legal puede firmar lo que va a firmar

Técnicamente ambas leen los mismos documentos en una pasada; la separación es
de compuertas, no de procesamiento.

**Tres niveles de gravedad**, porque no es lo mismo que falte un papel a que el
que hay no sirva:

  alta        el documento existe pero no es válido —una identificación
              vencida, una CSF de hace medio año, un contribuyente que no está
              ACTIVO—. No se avanza y no se acepta con justificación: se
              reemplaza.
  intermedia  falta un documento, o está por vencer. Cierra el paso a riesgo,
              pero cumplimiento lo puede aceptar por escrito si hay razón.
  baja        conviene saberlo y no detiene nada.

**Dos salidas**, como pide la especificación: una solicitud en lenguaje de
cliente para que ventas la copie tal cual, y el reporte completo para riesgo y
cumplimiento.
"""

from datetime import date, timedelta

from schema_expediente import (_get, UMBRAL_ESTADOS_CUENTA, ESTADOS_CUENTA_BASE,
                               ESTADOS_CUENTA_AMPLIADO)

ALTA, INTERMEDIA, BAJA = "alta", "intermedia", "baja"
ORDEN = {ALTA: 0, INTERMEDIA: 1, BAJA: 2}

MESES_CSF = 3
MESES_COMPROBANTE = 3
ANIOS_BURO = 3
DIAS_GRACIA_CORTE = 5      # un corte de hace menos de 5 días todavía no se exige

# Qué documentos se piden y cómo se le llaman al cliente. El nombre de la
# izquierda es el del schema; el de la derecha es el que ve ventas.
OBLIGATORIOS_PM = [
    ("csf_cliente",           "Constancia de Situación Fiscal de la empresa"),
    ("acta_constitutiva",     "Acta constitutiva (testimonio o copia certificada)"),
    ("comprobante_domicilio", "Comprobante de domicilio de la empresa"),
    ("identificacion_rep",    "Identificación oficial vigente del representante legal"),
    ("autorizacion_buro",     "Autorización de consulta de buró del representante"),
    ("credencial_sat",        "Credencial del SAT (usuario y contraseña del portal)"),
    ("cotizacion",            "Cotización firmada"),
]

OBLIGATORIOS_PF = [
    ("csf_cliente",           "Constancia de Situación Fiscal"),
    ("identificacion_rep",    "Identificación oficial vigente con fotografía"),
    ("comprobante_domicilio", "Comprobante de domicilio"),
    ("constancia_cuenta_propia", "Constancia de que actúa por cuenta propia o de un tercero"),
    ("autorizacion_buro",     "Autorización de consulta de buró"),
    ("credencial_sat",        "Credencial del SAT (usuario y contraseña del portal)"),
    ("cotizacion",            "Cotización firmada"),
]


# ─────────────────────────────────────────────────────────────────────────────
def _fecha(v):
    if isinstance(v, date):
        return v
    if not v:
        return None
    try:
        return date(*(int(x) for x in str(v)[:10].split("-")))
    except (ValueError, TypeError):
        return None


def _mas_meses(f, meses):
    if not f:
        return None
    a, m = f.year, f.month + meses
    a += (m - 1) // 12
    m = (m - 1) % 12 + 1
    dias = [31, 29 if (a % 4 == 0 and (a % 100 != 0 or a % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(a, m, min(f.day, dias[m - 1]))


def _pesos(v):
    return "$%s" % format(float(v), ",.2f") if v not in (None, "") else "—"


class Revision(object):
    """Acumula los hallazgos y sabe presentarlos."""

    def __init__(self):
        self.hallazgos = []

    def anotar(self, gravedad, asunto, detalle, pedir=None, tipo=None, motivo=None):
        """`pedir` y `motivo` son para el cliente; `detalle` para uso interno.

        La distinción importa: 'no hay ningún documento de tipo
        autorizacion_buro' es útil para nosotros e ilegible para el cliente.
        """
        self.hallazgos.append({
            "gravedad": gravedad, "asunto": asunto, "detalle": detalle,
            "motivo": motivo or detalle, "pedir": pedir,
            "tipo": tipo or "revision", "fecha": date.today().isoformat(),
        })

    def por_gravedad(self, g):
        return [h for h in self.hallazgos if h["gravedad"] == g]

    @property
    def aprobado(self):
        return not (self.por_gravedad(ALTA) or self.por_gravedad(INTERMEDIA))

    def ordenados(self):
        return sorted(self.hallazgos, key=lambda h: (ORDEN[h["gravedad"]], h["asunto"]))


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 1 · ¿están todos?
# ─────────────────────────────────────────────────────────────────────────────
def _documentos_por_tipo(exp):
    fuera = {}
    for d in _get(exp, "documentos", []):
        if d.get("superado_por"):
            continue
        fuera.setdefault(d.get("tipo"), []).append(d)
    return fuera


def _completitud(exp, r, hoy):
    tipo = _get(exp, "tipo_cliente")
    presentes = _documentos_por_tipo(exp)
    lista = OBLIGATORIOS_PM if tipo == "persona_moral" else OBLIGATORIOS_PF

    for clave, nombre in lista:
        if clave not in presentes:
            # Solo la inicial en minúscula: bajar todo destroza las siglas
            # ('credencial del sat').
            r.anotar(INTERMEDIA, "Falta " + nombre[:1].lower() + nombre[1:],
                     "No hay ningún documento de tipo %s en el expediente." % clave,
                     pedir=nombre, tipo="faltante",
                     motivo="No lo tenemos en el expediente.")

    # Estados de cuenta: la cantidad depende de la línea, y la línea puede subir
    # en riesgo, así que esto se vuelve a revisar más adelante.
    linea = (_get(exp, "credito.autorizada.linea")
             or _get(exp, "credito.solicitada.linea"))
    requeridos = (ESTADOS_CUENTA_AMPLIADO
                  if linea and float(linea) > UMBRAL_ESTADOS_CUENTA
                  else ESTADOS_CUENTA_BASE)

    cuentas = [c for c in _get(exp, "cuentas_bancarias", [])
               if c.get("titular_es_cliente")]
    periodos = max((len(c.get("periodos") or []) for c in cuentas), default=0)
    if periodos < requeridos:
        faltan = requeridos - periodos
        r.anotar(INTERMEDIA,
                 "Faltan %d estado(s) de cuenta" % faltan,
                 "Hay %d y con una línea de %s se requieren %d."
                 % (periodos, _pesos(linea), requeridos),
                 pedir=("%d estado(s) de cuenta bancarios más, de los meses más "
                        "recientes" % faltan),
                 tipo="estados_cuenta")

    # El corte más reciente que ya se puede exigir.
    corte_exigible = hoy - timedelta(days=DIAS_GRACIA_CORTE)
    for c in cuentas:
        ultimos = sorted(c.get("periodos") or [])
        if not ultimos:
            continue
        a, m = (int(x) for x in ultimos[-1].split("-")[:2])
        fin = _mas_meses(date(a, m, 1), 1) - timedelta(days=1)
        if fin < _mas_meses(corte_exigible, -1):
            r.anotar(INTERMEDIA, "Los estados de cuenta no llegan al mes exigible",
                     "El último es de %s; a hoy ya se puede exigir hasta el corte "
                     "anterior al %s." % (ultimos[-1], corte_exigible.isoformat()),
                     pedir="El estado de cuenta del mes más reciente ya cerrado",
                     tipo="estados_cuenta")

    if _get(exp, "flags.obligado_solidario"):
        os_ = _get(exp, "obligado_solidario", {})
        if os_.get("es_cliente") and not os_.get("expediente_ref"):
            r.anotar(INTERMEDIA, "Obligado solidario sin expediente referenciado",
                     "Se marcó que ya es cliente pero no se dijo cuál es su expediente.",
                     tipo="obligado_solidario")
        elif not os_.get("es_cliente"):
            nombre = os_.get("razon_social") or _get(exp, "obligado_solidario.persona_fisica.nombre")
            if not os_.get("rfc") and not _get(exp, "obligado_solidario.persona_fisica.rfc"):
                r.anotar(INTERMEDIA, "Faltan documentos del obligado solidario",
                         "Se registró %s como obligado pero no hay su documentación."
                         % (nombre or "un obligado"),
                         pedir=("Constancia de Situación Fiscal, acta constitutiva, "
                                "comprobante de domicilio e identificación del "
                                "obligado solidario"),
                         tipo="obligado_solidario")


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 2 · ¿sirven?
# ─────────────────────────────────────────────────────────────────────────────
def _vigencias(exp, r, hoy):
    presentes = _documentos_por_tipo(exp)

    def revisar(clave, nombre, meses=None, anios=None, exigir_vigencia=False):
        for d in presentes.get(clave, []):
            emision = _fecha(d.get("fecha_emision"))
            vence = _fecha(d.get("vigente_hasta"))
            if vence is None and emision:
                vence = (_mas_meses(emision, meses) if meses
                         else _mas_meses(emision, (anios or 0) * 12))
            if vence is None:
                if exigir_vigencia:
                    r.anotar(INTERMEDIA, "%s sin fecha de vigencia" % nombre,
                             "No se pudo determinar hasta cuándo es válido.",
                             pedir="Confirmar la vigencia de: %s" % nombre,
                             tipo="vigencia")
                continue

            if vence < hoy:
                dias = (hoy - vence).days
                # Un documento vencido no se acepta con justificación: se
                # reemplaza. Por eso es alta y no intermedia.
                r.anotar(ALTA, "%s vencido" % nombre,
                         "Venció el %s, hace %d día(s)." % (vence.isoformat(), dias),
                         pedir="%s vigente" % nombre, tipo="vigencia")
            elif (vence - hoy).days <= 15:
                r.anotar(INTERMEDIA, "%s por vencer" % nombre,
                         "Vence el %s, en %d día(s)." % (vence.isoformat(),
                                                         (vence - hoy).days),
                         pedir=("%s más reciente, porque el actual vence en %d día(s)"
                                % (nombre, (vence - hoy).days)),
                         tipo="vigencia")

    revisar("csf_cliente", "Constancia de Situación Fiscal", meses=MESES_CSF)
    revisar("csf_obligado_solidario", "CSF del obligado solidario", meses=MESES_CSF)
    revisar("csf_beneficiario", "CSF de beneficiario controlador", meses=MESES_CSF)
    revisar("comprobante_domicilio", "Comprobante de domicilio", meses=MESES_COMPROBANTE)
    revisar("autorizacion_buro", "Autorización de buró", anios=ANIOS_BURO)
    # Criterio Nea: la identificación debe estar vigente. El Manual admite hasta
    # dos años de vencida; aquí no.
    revisar("identificacion_rep", "Identificación del representante legal",
            exigir_vigencia=True)
    revisar("identificacion_beneficiario", "Identificación de beneficiario controlador",
            exigir_vigencia=True)

    for d in _get(exp, "documentos", []):
        if d.get("legible") is False:
            r.anotar(INTERMEDIA, "Documento ilegible: %s" % d.get("tipo"),
                     "No se puede leer con claridad.",
                     pedir="Volver a enviar, legible: %s" % d.get("tipo"),
                     tipo="legibilidad")

    if (_get(exp, "cliente.validado.situacion_contribuyente") or "").upper() not in ("", "ACTIVO"):
        r.anotar(ALTA, "El contribuyente no está ACTIVO ante el SAT",
                 "Situación: %s. El expediente no debe abrirse."
                 % _get(exp, "cliente.validado.situacion_contribuyente"),
                 tipo="compuerta")


def _coherencia(exp, r):
    """Que los documentos hablen de la misma empresa y de la misma persona."""
    def limpio(s):
        import re
        import unicodedata
        if not s:
            return None
        t = unicodedata.normalize("NFKD", str(s)).upper()
        t = "".join(c for c in t if not unicodedata.combining(c))
        t = re.sub(r"[^A-Z0-9 ]", " ", t)
        ruido = {"SA", "DE", "CV", "S", "A", "C", "V", "SAPI", "SC", "RL"}
        return " ".join(p for p in t.split() if p not in ruido)

    validada = _get(exp, "cliente.validado.razon_social")
    declarada = _get(exp, "cliente.declarado.razon_social")
    if validada and declarada and limpio(validada) != limpio(declarada):
        r.anotar(BAJA, "La razón social de la cotización no coincide con la CSF",
                 "La cotización dice %r y la constancia %r. El contrato se emite "
                 "con la de la constancia." % (declarada, validada),
                 tipo="coherencia")

    rfc_cliente = _get(exp, "cliente.validado.rfc")
    for c in _get(exp, "cuentas_bancarias", []):
        if not c.get("titular_es_cliente"):
            r.anotar(ALTA, "Estados de cuenta a nombre de otra entidad",
                     "La cuenta de %s está a nombre de %s, no del cliente. El "
                     "análisis de riesgo quedaría sobre el flujo de otra empresa."
                     % (c.get("banco") or "?", c.get("titular") or "?"),
                     pedir=("Estados de cuenta a nombre de la empresa solicitante, "
                            "no de una filial ni de la tenedora"),
                     tipo="coherencia")

    os_rfc = (_get(exp, "obligado_solidario.rfc")
              or _get(exp, "obligado_solidario.persona_fisica.rfc"))
    if _get(exp, "flags.obligado_solidario") and os_rfc and os_rfc == rfc_cliente:
        r.anotar(ALTA, "El obligado solidario es el mismo cliente",
                 "Ambos tienen el RFC %s. Una empresa no puede garantizarse a sí "
                 "misma." % os_rfc, tipo="coherencia")

    # Beneficiarios declarados sin su documentación.
    presentes = _documentos_por_tipo(exp)
    csfs = {(d.get("sujeto") or "").upper() for d in presentes.get("csf_beneficiario", [])}
    for b in _get(exp, "beneficiarios_controladores", []):
        nombre = b.get("nombre")
        if nombre and nombre.upper() not in csfs:
            r.anotar(INTERMEDIA,
                     "Falta documentación del beneficiario %s" % nombre,
                     "Está identificado como beneficiario controlador pero no hay "
                     "su CSF ni su identificación.",
                     pedir=("Constancia de Situación Fiscal e identificación oficial "
                            "vigente de %s" % nombre),
                     tipo="beneficiario")


# ─────────────────────────────────────────────────────────────────────────────
# Etapa 2 · facultades del representante
# ─────────────────────────────────────────────────────────────────────────────
def _elegibles(exp, linea=None):
    """Quién más podría firmar, según la constitutiva.

    Cuando el representante propuesto no sirve, no basta con decirlo: hay que
    decir quién sí, con nombre y fundamento. Si no, ventas vuelve a preguntar.
    """
    salida = []
    for a in _get(exp, "organo_administracion.apoderados", []) or []:
        if isinstance(a, dict):
            fac = a.get("facultades") or {}
            if fac.get("titulos_credito") is False:
                continue
            # De nada sirve proponer a alguien cuyo poder tampoco alcanza.
            tope = fac.get("limite_monto")
            if linea and tope is not None and float(tope) < float(linea):
                continue
            salida.append({"nombre": a.get("nombre"),
                           "cargo": a.get("cargo"),
                           "fundamento": a.get("fundamento"),
                           "limite": fac.get("limite_monto")})
        elif a:
            salida.append({"nombre": a, "cargo": None, "fundamento": None,
                           "limite": None})
    return salida


def _facultades(exp, r):
    """El árbol de decisión de la etapa 2, que es lo más consecuente del flujo."""
    val = _get(exp, "representante_legal.validado", {}) or {}
    nombre = val.get("nombre")
    fac = val.get("facultades") or {}
    linea = (_get(exp, "credito.autorizada.linea")
             or _get(exp, "credito.solicitada.linea"))

    if not nombre:
        propuesto = _get(exp, "representante_legal.propuesto.nombre")
        r.anotar(INTERMEDIA, "Falta validar las facultades del representante",
                 ("Ventas propuso a %s, pero todavía no se leen sus poderes. "
                  "Quién puede firmar sale de la escritura, no de quién se ofrezca."
                  % propuesto) if propuesto else
                 "No hay representante legal propuesto ni validado.",
                 pedir=("Escritura con los poderes del representante legal, o el "
                        "instrumento donde consten sus facultades"),
                 tipo="facultades")
        return

    lista = _elegibles(exp, linea)
    def sugerencia():
        if not lista:
            return ("Indicar quién sí tiene facultades para suscribir títulos de "
                    "crédito, y enviar el instrumento que lo acredite.")
        renglones = []
        for e in lista:
            t = "· %s" % e["nombre"]
            if e.get("cargo"):
                t += " (%s)" % e["cargo"]
            if e.get("limite"):
                t += " — hasta %s" % _pesos(e["limite"])
            if e.get("fundamento"):
                t += " — %s" % e["fundamento"]
            renglones.append(t)
        return ("Designar como firmante a alguien con facultades. Según la "
                "escritura, pueden hacerlo:\n" + "\n".join(renglones))

    # 1 · ¿puede suscribir títulos de crédito?
    if fac.get("titulos_credito") is not True:
        r.anotar(ALTA, "El representante no puede suscribir títulos de crédito",
                 "%s no tiene esa facultad, y el contrato de crédito la exige."
                 % nombre,
                 pedir=sugerencia(), tipo="facultades")
        return

    # 2 · ¿la ejerce solo?
    if fac.get("individual") is not True:
        cofirmantes = _get(exp, "cofirmantes", [])
        if not cofirmantes:
            r.anotar(INTERMEDIA, "El poder es mancomunado y faltan los cofirmantes",
                     "%s solo puede firmar junto con otro apoderado, y no hay "
                     "ninguno registrado." % nombre,
                     pedir=("Identificación oficial vigente de los apoderados que "
                            "deben firmar junto con %s" % nombre),
                     tipo="facultades")
        else:
            r.anotar(BAJA, "El poder es mancomunado",
                     "Firman junto con %s: %s." % (
                         nombre, ", ".join(
                             c if isinstance(c, str) else c.get("nombre", "?")
                             for c in cofirmantes)),
                     tipo="facultades")

    # 3 · ¿alcanza el límite del poder?
    limite = fac.get("limite_monto")
    if limite is not None and linea and float(limite) < float(linea):
        r.anotar(ALTA, "El poder no alcanza para el monto solicitado",
                 "El poder de %s tiene un límite de %s y la línea es de %s."
                 % (nombre, _pesos(limite), _pesos(linea)),
                 pedir=sugerencia(), tipo="facultades")
    elif limite is None:
        r.anotar(BAJA, "El poder no declara límite de monto",
                 "Se entiende sin límite. Si la escritura sí lo tiene, hay que "
                 "capturarlo antes de autorizar la línea.", tipo="facultades")


# ─────────────────────────────────────────────────────────────────────────────
def revisar(exp, hoy=None):
    """Corre las etapas 1 y 2 completas."""
    hoy = hoy or date.today()
    r = Revision()
    _completitud(exp, r, hoy)
    _vigencias(exp, r, hoy)
    _coherencia(exp, r)
    _facultades(exp, r)
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Salidas
# ─────────────────────────────────────────────────────────────────────────────
ENCABEZADOS = {
    ALTA: "Documentos que no podemos aceptar como están",
    INTERMEDIA: "Documentos que nos faltan",
    BAJA: "Detalles menores",
}


def solicitud_para_ventas(exp, r):
    """El texto que ventas copia y le manda al cliente.

    En lenguaje de cliente y agrupado por gravedad, para que se entienda qué es
    urgente. Sin jerga interna ni nombres de campo.
    """
    razon = _get(exp, "cliente.validado.razon_social") or "el cliente"
    folio = _get(exp, "folio") or ""

    if r.aprobado:
        return ("Expediente %s — %s\n\n"
                "Revisión completa: la documentación está completa y vigente.\n"
                "Pasa a análisis de riesgo." % (folio, razon))

    lineas = ["Expediente %s — %s" % (folio, razon), "",
              "Revisamos la documentación y necesitamos lo siguiente para continuar:", ""]

    for gravedad in (ALTA, INTERMEDIA):
        grupo = [h for h in r.por_gravedad(gravedad) if h.get("pedir")]
        if not grupo:
            continue
        lineas.append(ENCABEZADOS[gravedad].upper())
        for h in grupo:
            lineas.append("")
            pedido = str(h["pedir"]).splitlines()
            lineas.append("  %s" % pedido[0])
            lineas.extend("      %s" % x for x in pedido[1:])
            lineas.append("      Motivo: %s" % h["motivo"])
        lineas.append("")

    menores = r.por_gravedad(BAJA)
    if menores:
        lineas.append("Para tu información, sin que detenga el trámite:")
        for h in menores:
            lineas.append("  · %s" % h["asunto"])
        lineas.append("")

    lineas.append("En cuanto lo tengamos seguimos con el análisis.")
    return "\n".join(lineas)


def reporte_interno(exp, r):
    """El reporte completo, para riesgo y cumplimiento."""
    folio = _get(exp, "folio") or "?"
    lineas = ["REVISIÓN DE EXPEDIENTE %s" % folio,
              "%s · %s" % (_get(exp, "cliente.validado.razon_social") or "?",
                           _get(exp, "cliente.validado.rfc") or "?"),
              "Fecha de revisión: %s" % date.today().isoformat(), ""]

    conteo = {g: len(r.por_gravedad(g)) for g in (ALTA, INTERMEDIA, BAJA)}
    lineas.append("Resultado: %s" % ("APROBADO — pasa a riesgo" if r.aprobado
                                     else "INCOMPLETO — regresa a recolección"))
    lineas.append("Gravedad alta: %d · intermedia: %d · baja: %d"
                  % (conteo[ALTA], conteo[INTERMEDIA], conteo[BAJA]))
    lineas.append("")

    for gravedad in (ALTA, INTERMEDIA, BAJA):
        grupo = r.por_gravedad(gravedad)
        if not grupo:
            continue
        lineas.append("── %s ──" % ENCABEZADOS[gravedad])
        for h in grupo:
            lineas.append("  [%s] %s" % (h["tipo"], h["asunto"]))
            lineas.append("      %s" % h["detalle"])
        lineas.append("")
    return "\n".join(lineas)


def a_observaciones(exp, r):
    """Vuelca los hallazgos al expediente, sin duplicar los que ya estaban."""
    ya = {(o.get("tipo"), o.get("descripcion")) for o in exp.get("observaciones", [])}
    nuevas = 0
    for h in r.hallazgos:
        desc = "%s — %s" % (h["asunto"], h["detalle"])
        if (h["tipo"], desc) in ya:
            continue
        exp["observaciones"].append({
            "tipo": h["tipo"], "descripcion": desc, "severidad": h["gravedad"],
            "estado": "abierta", "fecha": h["fecha"],
        })
        nuevas += 1
    return nuevas
