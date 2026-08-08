# -*- coding: utf-8 -*-
"""
perfil_empresa.py — El módulo de perfil, expandido
===================================================
El perfil original eran cinco variables y cuatro se capturaban a mano. Tres de
esas cuatro las sabe Syntage y las venimos pagando sin usarlas.

Este módulo hace dos cosas:

  `derivar()`   saca del expediente y de los payloads de Syntage todo lo que se
                puede saber sin preguntarle nada a nadie.
  `evaluar()`   califica el perfil completo. Sustituye a `_perfil_empresa` del
                modelo, con la misma firma de salida: {variable: (peso, puntaje)}.

**Qué NO está aquí, y por qué.** Los importes facturados, el margen y los días
de cobro no entran al perfil aunque Syntage los dé: se van al módulo de
declaración anual, que es donde viven las magnitudes financieras. Meterlos en
los dos lados los contaría dos veces sobre un mismo hecho. Lo que el perfil sí
mira de la facturación es si existe —cuántos meses, cuántos CFDI, cuántos
empleados—, que es una pregunta distinta: no cuánto vende, sino si opera.

**La presencia digital se captura como hechos, no como calificación.** Antes se
le pedía al operador una nota "Alta/Media/Baja", que es pedirle que haga el
juicio que debería hacer el modelo: dos analistas veían la misma empresa y
escribían cosas distintas. Ahora se capturan el sitio, cada red con sus
seguidores y la fecha de la última publicación, y la nota se calcula.
"""

from datetime import date, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# Pesos. Suman 1.00, pero el modelo renormaliza sobre las variables que sí
# tienen dato, así que una ausencia no arrastra al módulo.
PESOS = {
    # quién es
    "giro":                     0.15,
    "antiguedad":               0.12,
    "estado":                   0.08,
    # si de verdad opera
    "empleados":                0.08,
    "actividad_facturada":      0.12,
    # con quién opera
    "concentracion_clientes":   0.07,
    "concentracion_proveedores": 0.07,
    "partes_relacionadas":      0.06,
    # cómo se porta
    "cumplimiento":             0.15,
    # cómo se ve y de dónde vino
    "presencia_digital":        0.06,
    "procedencia":              0.04,
}

# Tabla de Estado, tal como la fija la especificación: PIB per cápita y
# siniestralidad logística —robo a autotransporte, no criminalidad general—.
# Se deriva del domicilio fiscal; no se captura.
ESTADO_CODIGO_1 = {
    "AGUASCALIENTES", "BAJA CALIFORNIA SUR", "CIUDAD DE MEXICO", "COAHUILA",
    "COAHUILA DE ZARAGOZA", "JALISCO", "NUEVO LEON", "QUERETARO", "YUCATAN",
}
ESTADO_CODIGO_2 = {
    "BAJA CALIFORNIA", "CHIHUAHUA", "MEXICO", "ESTADO DE MEXICO", "GUANAJUATO",
    "PUEBLA", "QUINTANA ROO", "SAN LUIS POTOSI", "SONORA",
}

# El RFC genérico del público en general. Un 80% de ventas contra este RFC no
# es concentración de clientes: es mostrador. Contarlo como concentración
# castigaría a cualquier negocio de venta al menudeo.
RFC_PUBLICO_GENERAL = "XAXX010101000"
RFC_EXTRANJERO = "XEXX010101000"

# Las 13 banderas que Syntage precalcula. Se cuentan las que vienen en rojo.
BANDERAS = ("taxCompliance", "blacklistStatus", "moratoryInterest",
            "cashTransactionRisk", "foreignExchangeRisk", "accountingInsolvency",
            "customerConcentration", "supplierConcentration",
            "canceledIssuedInvoices", "infonavitOverdueCredits",
            "canceledReceivedInvoices", "intercompanyTransactions",
            "blacklistedCounterparties")


def _sin_acentos(t):
    tabla = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N",
             "á": "A", "é": "E", "í": "I", "ó": "O", "ú": "U", "ñ": "N"}
    return "".join(tabla.get(c, c) for c in (t or "")).upper().strip()


def _fecha(v):
    if isinstance(v, date) or v is None:
        return v
    try:
        return date(*(int(x) for x in str(v)[:10].split("-")))
    except (ValueError, TypeError):
        return None


def codigo_estado(nombre):
    """El código de la tabla de Estado a partir del nombre del estado."""
    e = _sin_acentos(nombre)
    if not e:
        return None
    if e in ESTADO_CODIGO_1:
        return "Codigo 1"
    if e in ESTADO_CODIGO_2:
        return "Codigo 2"
    return "Codigo 3"


# ─────────────────────────────────────────────────────────────────────────────
# Lo que se deriva sin preguntar
# ─────────────────────────────────────────────────────────────────────────────
def _top_contraparte(payload, excluir_rfc=()):
    """La contraparte con mayor participación, ignorando los RFC genéricos.

    Devuelve (share, nombre, rfc). El público en general y el RFC de
    extranjeros se excluyen: no son un cliente, son una categoría.
    """
    fuera = None
    excluir = {RFC_PUBLICO_GENERAL, RFC_EXTRANJERO} | set(excluir_rfc or ())
    for c in (payload or {}).get("data") or []:
        if (c.get("rfc") or "").upper() in excluir:
            continue
        if fuera is None or (c.get("share") or 0) > fuera[0]:
            fuera = ((c.get("share") or 0.0), c.get("name"), c.get("rfc"))
    return fuera or (None, None, None)


def _share_de(payload, rfcs):
    """Suma la participación de un conjunto de RFC dentro de un insight."""
    if not rfcs:
        return None
    rfcs = {(r or "").upper() for r in rfcs if r}
    total, visto = 0.0, False
    for c in (payload or {}).get("data") or []:
        if (c.get("rfc") or "").upper() in rfcs:
            total += c.get("share") or 0.0
            visto = True
    return total if visto else 0.0


def _ultimo_anio_facturado(comparativo):
    """(ejercicio, ingresos, cfdi) del último año con facturación emitida."""
    mejor = (None, None)
    for p in comparativo or []:
        if not str(p.get("period", "")).isdigit():
            continue          # la fila "Acumulado"
        ingreso = p.get("totalIncome")
        try:
            ingreso = float(ingreso)
        except (TypeError, ValueError):
            continue
        anio = int(p["period"])
        if ingreso > 0 and (mejor[0] is None or anio > mejor[0]):
            mejor = (anio, ingreso)
    return mejor


def derivar(exp, payloads, hoy=None):
    """Todo lo que se puede saber del perfil sin capturar nada.

    `payloads` es {recurso: payload} tal como quedaron en `syntage_datos`.
    Devuelve el diccionario de perfil, con las claves que `evaluar()` consume.
    """
    from schema_expediente import _get

    hoy = hoy or date.today()
    resumen = payloads.get("summary") or {}
    p = {}

    # Estado y antigüedad: del domicilio fiscal y del alta ante el SAT.
    p["estado_nombre"] = _get(resumen, "address.state")
    p["estado"] = codigo_estado(p["estado_nombre"])
    p["fecha_constitucion"] = (_fecha(resumen.get("registrationDate"))
                               or _fecha(_get(exp, "cliente.validado.fecha_constitucion")))

    # Giro: la actividad SCIAN se deriva; el código de ciclo de conversión NO,
    # porque la tabla de seis códigos no está en ningún lado del repositorio.
    # Hasta que exista, el operador escoge el código viendo la actividad.
    p["actividades"] = [a.get("name") for a in resumen.get("economicActivities") or []]
    p["actividad_principal"] = p["actividades"][0] if p["actividades"] else None

    # Sustancia operativa.
    p["empleados"] = resumen.get("totalEmployees")
    anio, ingresos = _ultimo_anio_facturado(payloads.get("metrics/invoicing-annual-comparison"))
    p["ultimo_anio_facturado"] = anio
    p["ingresos_cfdi"] = ingresos
    p["cfdi_emitidos"] = sum(
        (x.get("transactions") or 0)
        for x in (payloads.get("sales-revenue") or {}).get("data") or [])
    p["anios_con_facturacion"] = len([
        x for x in (payloads.get("metrics/invoicing-annual-comparison") or [])
        if str(x.get("period", "")).isdigit() and _positivo(x.get("totalIncome"))])

    # Estructura comercial.
    share_c, nombre_c, rfc_c = _top_contraparte(payloads.get("customer-concentration"))
    share_p, nombre_p, rfc_p = _top_contraparte(payloads.get("supplier-concentration"))
    p["top_cliente"] = {"share": share_c, "nombre": nombre_c, "rfc": rfc_c}
    p["top_proveedor"] = {"share": share_p, "nombre": nombre_p, "rfc": rfc_p}

    gob = (payloads.get("government-customers") or {}).get("data") or []
    p["ventas_gobierno"] = sum(g.get("share") or 0.0 for g in gob)

    # Compras a la propia garantía. Que el obligado solidario sea además el
    # proveedor principal no diversifica nada: es el mismo riesgo dos veces.
    rfcs_relacionados = [
        _get(exp, "obligado_solidario.rfc"),
        _get(exp, "obligado_solidario.persona_fisica.rfc"),
    ]
    p["rfcs_relacionados"] = [r for r in rfcs_relacionados if r]
    p["compras_partes_relacionadas"] = _share_de(
        payloads.get("supplier-concentration"), p["rfcs_relacionados"])
    p["ventas_partes_relacionadas"] = _share_de(
        payloads.get("customer-concentration"), p["rfcs_relacionados"])

    # Cumplimiento: las banderas que Syntage ya calculó.
    riesgos = (payloads.get("risks") or {}).get("data") or {}
    p["banderas_rojas"] = sorted(b for b in BANDERAS
                                 if (riesgos.get(b) or {}).get("risky") is True)
    p["banderas_evaluadas"] = sorted(b for b in BANDERAS if b in riesgos)
    p["riesgos_detalle"] = riesgos

    return p


def _positivo(v):
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Presencia digital: hechos capturados, nota calculada
# ─────────────────────────────────────────────────────────────────────────────
DIAS_RED_ACTIVA = 90


def nota_presencia_digital(pd, hoy=None):
    """De {sitio_web, redes:[{red, seguidores, ultima_publicacion}]} a un 0–1.

    Devuelve (nota, desglose). Nota None si no se capturó nada: no saber si la
    empresa tiene redes no es lo mismo que saber que no tiene.
    """
    if not pd:
        return None, {}
    hoy = hoy or date.today()
    corte = hoy - timedelta(days=DIAS_RED_ACTIVA)

    tiene_sitio = bool(pd.get("sitio_web"))
    redes = pd.get("redes") or []
    activas = [r for r in redes
               if (_fecha(r.get("ultima_publicacion")) or date.min) >= corte]
    seguidores = sum(r.get("seguidores") or 0 for r in redes)

    # Si el operador no capturó ni sitio ni redes ni un "no tiene" explícito,
    # no hay nada que calificar.
    if not tiene_sitio and not redes and not pd.get("sin_presencia"):
        return None, {}

    n_sitio = 0.35 if tiene_sitio else 0.0
    n_redes = {0: 0.0, 1: 0.20, 2: 0.30}.get(len(activas), 0.40)
    n_seg = (0.25 if seguidores >= 10000 else
             0.18 if seguidores >= 2000 else
             0.12 if seguidores >= 500 else
             0.06 if seguidores >= 100 else 0.0)

    desglose = {"sitio_web": n_sitio, "redes_activas": n_redes,
                "seguidores": n_seg, "num_redes_activas": len(activas),
                "seguidores_totales": seguidores}
    return round(min(1.0, n_sitio + n_redes + n_seg), 4), desglose


# ─────────────────────────────────────────────────────────────────────────────
# La calificación del módulo
# ─────────────────────────────────────────────────────────────────────────────
def _escalon(valor, tramos, default):
    if valor is None:
        return None
    for prueba, puntaje in tramos:
        if prueba(valor):
            return puntaje
    return default


def evaluar(p, hoy=None):
    """{variable: (peso, puntaje)}, con la misma forma que los otros módulos.

    Un puntaje None saca la variable del promedio; el modelo renormaliza. Eso
    es deliberado en todas: la ausencia de un dato no es un dato desfavorable.
    """
    hoy = hoy or date.today()
    v = {}

    v["estado"] = (PESOS["estado"],
                   {"Codigo 1": 1.0, "Codigo 2": 0.75, "Codigo 3": 0.5}
                   .get(p.get("estado")))

    fc = _fecha(p.get("fecha_constitucion"))
    antiguedad = (hoy - fc).days / 365 if fc else None
    v["antiguedad"] = (PESOS["antiguedad"], _escalon(antiguedad, [
        (lambda x: x >= 9, 1.0), (lambda x: x >= 4, 0.7),
        (lambda x: x >= 2, 0.5)], 0.25))

    v["giro"] = (PESOS["giro"],
                 {"Codigo 1": 1.0, "Codigo 2": 0.8, "Codigo 3": 0.65,
                  "Codigo 4": 0.5, "Codigo 5": 0.3, "Codigo 6": 0.15}
                 .get(p.get("giro")))

    # Cero empleados no descalifica —hay negocios que subcontratan todo— pero
    # tampoco es neutro: no hay nómina que respalde la operación.
    v["empleados"] = (PESOS["empleados"], _escalon(p.get("empleados"), [
        (lambda x: x >= 20, 1.0), (lambda x: x >= 5, 0.75),
        (lambda x: x >= 1, 0.5)], 0.25))

    # ¿Opera, o solo existe? Se mide en años con facturación y en volumen de
    # CFDI, no en pesos: los pesos son del módulo fiscal.
    anios = p.get("anios_con_facturacion")
    cfdi = p.get("cfdi_emitidos")
    nota_anios = _escalon(anios, [
        (lambda x: x >= 3, 1.0), (lambda x: x == 2, 0.75),
        (lambda x: x == 1, 0.5)], 0.0)
    nota_cfdi = _escalon(cfdi, [
        (lambda x: x >= 500, 1.0), (lambda x: x >= 100, 0.75),
        (lambda x: x >= 20, 0.5), (lambda x: x >= 1, 0.25)], 0.0)
    partes = [n for n in (nota_anios, nota_cfdi) if n is not None]
    v["actividad_facturada"] = (PESOS["actividad_facturada"],
                                sum(partes) / len(partes) if partes else None)

    top_c = (p.get("top_cliente") or {}).get("share")
    v["concentracion_clientes"] = (PESOS["concentracion_clientes"], _escalon(top_c, [
        (lambda x: x <= 25, 1.0), (lambda x: x <= 40, 0.75),
        (lambda x: x <= 60, 0.5), (lambda x: x <= 80, 0.25)], 0.0))

    top_p = (p.get("top_proveedor") or {}).get("share")
    v["concentracion_proveedores"] = (PESOS["concentracion_proveedores"], _escalon(top_p, [
        (lambda x: x <= 30, 1.0), (lambda x: x <= 50, 0.75),
        (lambda x: x <= 70, 0.5), (lambda x: x <= 85, 0.25)], 0.0))

    # Operar con la propia garantía no diversifica: si el garante deja de
    # comprarle, el acreditado se queda sin ingresos Y sin garantía útil.
    rel = max(x for x in (p.get("compras_partes_relacionadas"),
                          p.get("ventas_partes_relacionadas"), -1.0)
              if x is not None)
    rel = None if rel < 0 else rel
    v["partes_relacionadas"] = (PESOS["partes_relacionadas"], _escalon(rel, [
        (lambda x: x <= 10, 1.0), (lambda x: x <= 25, 0.75),
        (lambda x: x <= 50, 0.5), (lambda x: x <= 75, 0.25)], 0.0))

    # Las banderas se cuentan solo si Syntage las evaluó. Si no vino el recurso
    # `risks`, cero banderas rojas no significa que esté limpio.
    rojas = p.get("banderas_rojas")
    evaluadas = p.get("banderas_evaluadas")
    v["cumplimiento"] = (PESOS["cumplimiento"],
                         None if not evaluadas else
                         _escalon(len(rojas or []), [
                             (lambda x: x == 0, 1.0), (lambda x: x == 1, 0.6),
                             (lambda x: x == 2, 0.3)], 0.0))

    nota_pd, _ = nota_presencia_digital(p.get("presencia_digital"), hoy)
    v["presencia_digital"] = (PESOS["presencia_digital"], nota_pd)

    # `procedencia_lead` y no `procedencia`: en el expediente `procedencia` ya
    # significa otra cosa —de qué documento salió cada campo— y confundirlas
    # metería rutas de archivo en una variable del modelo. Se acepta el nombre
    # viejo para no romper lo que ya estaba escrito.
    proc = p.get("procedencia_lead", p.get("procedencia"))
    v["procedencia"] = (PESOS["procedencia"], None if proc is None else
                        {"Conocido Nea": 1.0, "Referido Cliente": 0.75,
                         "Linkedin/Expo": 0.5}.get(proc, 0.25))
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Persistencia
# ─────────────────────────────────────────────────────────────────────────────
DERIVADOS = ("estado_nombre", "actividad_principal", "actividades", "empleados",
             "fecha_constitucion",
             "cfdi_emitidos", "anios_con_facturacion", "ultimo_anio_facturado",
             "ingresos_cfdi", "top_cliente", "top_proveedor", "ventas_gobierno",
             "compras_partes_relacionadas", "ventas_partes_relacionadas",
             "banderas_rojas", "banderas_evaluadas", "riesgos_detalle")

MANUALES = ("giro_codigo", "procedencia_lead", "presencia_digital")


def payloads_de(folio, sb=None):
    """{recurso: payload} de todo lo guardado de Syntage para un expediente."""
    import db
    sb = sb or db.cliente()
    filas = sb.table("syntage_datos").select("recurso,payload") \
              .eq("folio", folio).execute().data or []
    return {f["recurso"]: f["payload"] for f in filas}


def guardar(folio, perfil, sb=None):
    """Escribe el perfil sin pisar lo que capturó el operador.

    Volver a derivar es barato y se hará muchas veces —cada vez que se
    reextraiga Syntage—. El giro, la procedencia y la presencia digital costaron
    trabajo humano: solo se escriben si vienen en `perfil`.
    """
    import db
    sb = sb or db.cliente()
    fila = {"folio": folio, "estado_codigo": perfil.get("estado")}
    for c in DERIVADOS:
        if c in perfil:
            fila[c] = perfil[c]
    for c in MANUALES:
        if perfil.get(c) is not None:
            fila[c] = perfil[c]
    fc = fila.get("fecha_constitucion")
    if isinstance(fc, date):
        fila["fecha_constitucion"] = fc.isoformat()
    sb.table("perfil_empresa").upsert(fila, on_conflict="folio").execute()
    return fila


def cargar(folio, sb=None):
    """El perfil guardado, con las claves que `evaluar()` espera."""
    import db
    sb = sb or db.cliente()
    try:
        filas = sb.table("perfil_empresa").select("*").eq("folio", folio).execute().data
    except Exception as e:
        # Sin la tabla no hay perfil, que para el modelo es lo mismo que un
        # perfil sin capturar: el módulo sale del promedio. Se avisa en vez de
        # tragárselo, porque un módulo ausente sube el score de los demás.
        msg = str(e).lower()
        if "perfil_empresa" in msg and ("does not exist" in msg
                                        or "could not find the table" in msg):
            print("  (falta correr migracion_07_perfil.sql; el perfil no se evalúa)")
            return {}
        raise
    if not filas:
        return {}
    f = filas[0]
    p = {c: f.get(c) for c in DERIVADOS + MANUALES}
    p["estado"] = f.get("estado_codigo")
    p["giro"] = f.get("giro_codigo")
    return p


def refrescar(folio, exp=None, sb=None, hoy=None):
    """Deriva de Syntage, conserva lo capturado, guarda y devuelve el perfil."""
    import db
    sb = sb or db.cliente()
    if exp is None:
        exp = sb.table("expedientes").select("datos").eq("folio", folio) \
                .execute().data[0]["datos"]
    p = derivar(exp, payloads_de(folio, sb), hoy)
    guardado = cargar(folio, sb)
    for c in MANUALES:
        if guardado.get(c) is not None:
            p[c] = guardado[c]
    p["giro"] = guardado.get("giro")
    guardar(folio, p, sb)
    return p
