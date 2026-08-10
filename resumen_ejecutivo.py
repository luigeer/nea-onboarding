# -*- coding: utf-8 -*-
"""
resumen_ejecutivo.py — Lo que el score no dice
===============================================
Un score es un número y una decisión de crédito no lo es. Este módulo no
reescribe el score: escribe lo que el score no pudo capturar, que es la razón
por la que existe un comité.

Tres tipos de cosas entran:

  **Cobertura**      sobre qué se calculó. Un 0.71 con cuatro módulos y un 0.71
                     con dos no son el mismo 0.71, y el número se ve igual.
  **Señales**        hechos que mueven la decisión y ninguna variable del modelo
                     mira: capital contable negativo, ingresos que no pasan por
                     el banco, un garante controlado por el mismo dueño.
  **Observaciones**  lo que un humano anotó al revisar los documentos.

Las señales se **derivan** de los datos, no se escriben a mano por cliente. Si
mañana entra otra empresa con capital negativo, sale sola. Lo que se anota a
mano son las observaciones, que es donde vive el juicio.

**Qué NO hace este módulo:** recomendar. Ordena los hechos por qué tanto pesan
y deja la decisión a quien la firma. La tentación de cerrar con "se recomienda
aprobar" es fuerte y está mal: el resumen que decide por el comité deja de ser
un resumen.
"""

from datetime import date

ALTA, MEDIA, BAJA = "alta", "media", "baja"
ORDEN = {ALTA: 0, MEDIA: 1, BAJA: 2}

# Cómo se llama cada bandera de Syntage en español, y qué tan grave es que salga
# en rojo. Insolvencia contable e intereses moratorios pesan distinto que una
# concentración alta: las primeras describen a una empresa que ya no puede
# pagar, la segunda a una que depende de alguien.
BANDERAS = {
    "accountingInsolvency":     (ALTA,  "insolvencia contable"),
    "moratoryInterest":         (ALTA,  "intereses moratorios ya cobrados"),
    "blacklistStatus":          (ALTA,  "aparece en la lista 69-B del SAT"),
    "taxCompliance":            (ALTA,  "incumplimiento de obligaciones fiscales"),
    "blacklistedCounterparties": (MEDIA, "opera con contrapartes en la lista 69-B"),
    "supplierConcentration":    (MEDIA, "concentración de proveedores"),
    "customerConcentration":    (MEDIA, "concentración de clientes"),
    "canceledReceivedInvoices": (MEDIA, "facturas recibidas canceladas"),
    "canceledIssuedInvoices":   (MEDIA, "facturas emitidas canceladas"),
    "cashTransactionRisk":      (MEDIA, "operaciones en efectivo"),
    "infonavitOverdueCredits":  (MEDIA, "créditos Infonavit vencidos"),
    "intercompanyTransactions": (BAJA,  "operaciones intercompañía"),
    "foreignExchangeRisk":      (BAJA,  "exposición cambiaria"),
}

# Cuántas veces tiene que ser mayor la facturación que los depósitos bancarios
# para decir que el dinero no pasa por la cuenta que nos dieron. Se deja holgado
# a propósito: una empresa puede cobrar parte en otra cuenta sin que eso sea un
# hallazgo, y acusar en falso cuesta credibilidad.
FACTOR_NO_BANCARIZADO = 3.0


def _pesos(v):
    return "$%s" % format(float(v), ",.2f") if v not in (None, "") else "—"


def _pct(v):
    return "%.1f%%" % (float(v) * 100) if v not in (None, "") else "—"


class Senal(object):
    """Un hecho que mueve la decisión y que el modelo no mira."""

    def __init__(self, peso, titulo, detalle, fuente):
        self.peso, self.titulo, self.detalle, self.fuente = peso, titulo, detalle, fuente

    def __repr__(self):
        return "<Senal %s %s>" % (self.peso, self.titulo)


# ─────────────────────────────────────────────────────────────────────────────
# Señales derivadas de los datos
# ─────────────────────────────────────────────────────────────────────────────
def _senales_fiscales(fiscal):
    """Capital contable negativo y pérdida de operación.

    Ninguna variable del modelo mira el SIGNO del capital contable: la variable
    `capital_contable_entre_monto` divide y cae al peor tramo, que es lo mismo
    que le pasa a una empresa con poco capital. No es lo mismo tener poco
    capital que haberse comido el que había.
    """
    fuera = []
    for f in fiscal or []:
        cap, ej = f.get("capital_contable"), f.get("ejercicio")
        if cap is not None and cap < 0:
            fuera.append(Senal(
                ALTA, "Capital contable negativo en %s" % ej,
                "%s. Las pérdidas acumuladas superan el capital aportado. Bajo el "
                "artículo 229 de la Ley General de Sociedades Mercantiles esto puede "
                "ser causa de disolución." % _pesos(cap),
                "declaración anual %s" % ej))
        uo = f.get("utilidad_operacion")
        if uo is not None and uo < 0:
            fuera.append(Senal(
                MEDIA, "Pérdida de operación en %s" % ej,
                "%s sobre ingresos de %s. La operación no cubre sus propios costos."
                % (_pesos(uo), _pesos(f.get("ingresos_totales"))),
                "declaración anual %s" % ej))
    return fuera


def _senales_declaracion_vacia(fiscal):
    """Un ejercicio declarado en ceros entre dos ejercicios con cifras.

    No afecta el score —el modelo usa el más reciente con datos— y es
    exactamente el tipo de cosa que hay que preguntar.
    """
    con_datos = sorted(f.get("ejercicio") for f in (fiscal or [])
                       if (f.get("ingresos_totales") or 0) > 0)
    if len(con_datos) < 2:
        return []
    fuera = []
    for f in fiscal or []:
        ej = f.get("ejercicio")
        if (f.get("ingresos_totales") or 0) == 0 and con_datos[0] < ej < con_datos[-1]:
            fuera.append(Senal(
                MEDIA, "El ejercicio %s se declaró en ceros" % ej,
                "Está entre %s y %s, que traen cifras. Una empresa de ese tamaño "
                "declarando cero un año es algo que hay que preguntar antes de usar "
                "sus estados financieros." % (con_datos[0], con_datos[-1]),
                "declaración anual %s" % ej))
    return fuera


def _senales_banderas(perfil):
    fuera = []
    detalle = (perfil or {}).get("riesgos_detalle") or {}
    for clave in (perfil or {}).get("banderas_rojas") or []:
        peso, nombre = BANDERAS.get(clave, (BAJA, clave))
        valor = (detalle.get(clave) or {}).get("value")
        fuera.append(Senal(
            peso, "Syntage marca %s" % nombre,
            "Indicador en rojo con valor %s." % (valor if valor is not None else "s/d"),
            "insight `risks` de Syntage"))
    return fuera


def _senal_no_bancarizado(perfil, cuentas_meta, cfdi):
    """Facturación muy por encima de lo que entra al banco.

    El modelo lee los estados de cuenta y la facturación por separado y nunca
    los compara. Si una empresa factura diez veces lo que recibe en la cuenta
    que entregó, el análisis de capacidad de pago se hizo sobre la cuenta
    equivocada, y el score de ese módulo no significa lo que parece.
    """
    facturado = (cfdi or {}).get("ingresos_netos_acumulados")
    meses = (cfdi or {}).get("meses_transcurridos")
    depositos = (cuentas_meta or {}).get("depositos_mensuales")
    if not facturado or not meses or not depositos:
        return []
    mensual = facturado / meses
    if mensual < depositos * FACTOR_NO_BANCARIZADO:
        return []
    return [Senal(
        ALTA, "El dinero facturado no pasa por la cuenta entregada",
        "Factura alrededor de %s al mes y por la cuenta que entregó entran %s. "
        "El análisis de capacidad de pago se hizo sobre una cuenta que no recibe "
        "los ingresos del negocio."
        % (_pesos(mensual), _pesos(depositos)),
        "CFDI de Syntage contra los estados de cuenta")]


def _senal_cuentas_por_pagar(cfdi):
    cxp = (cfdi or {}).get("cuentas_por_pagar")
    if not cxp:
        return []
    pagado = (cfdi or {}).get("pct_credito_pagado")
    credito = (cfdi or {}).get("pct_compras_a_credito")
    extra = ""
    if credito is not None and pagado is not None:
        extra = (" El %s de sus compras es a crédito y solo lleva pagado el %s de eso."
                 % (_pct(credito), _pct(pagado)))
    return [Senal(
        ALTA, "Cuentas por pagar pendientes por %s" % _pesos(cxp),
        "Ninguna variable del modelo mira el pasivo con proveedores.%s Compite "
        "directamente con el pago de la línea." % extra,
        "CFDI de Syntage")]


def _senal_sin_empleados(perfil):
    if (perfil or {}).get("empleados") != 0:
        return []
    return [Senal(
        MEDIA, "Cero empleados registrados",
        "No hay nómina que respalde la operación. Puede ser subcontratación "
        "legítima, y también puede ser que la actividad la realice otra empresa.",
        "padrón del SAT vía Syntage")]


def _senal_buro_sin_historial(buro):
    if (buro or {}).get("resultado") != "sin_historial":
        return []
    return [Senal(
        MEDIA, "Sin historial en buró de crédito",
        "La consulta se hizo (folio %s) y el buró no tiene nada. No es un mal "
        "historial: es la ausencia de historial, y por eso el módulo de buró —25%% "
        "del score— salió del promedio y los otros tres se renormalizaron."
        % ((buro or {}).get("folio_consulta") or "s/d"),
        "consulta de buró")]


def _senal_partes_relacionadas(perfil, garante):
    """Comprar o vender a su propio garante no diversifica el riesgo."""
    fuera = []
    compras = (perfil or {}).get("compras_partes_relacionadas")
    ventas = (perfil or {}).get("ventas_partes_relacionadas")
    nombre = (garante or {}).get("razon_social") or "su obligado solidario"
    if compras and compras > 25:
        fuera.append(Senal(
            ALTA, "El %s de sus compras son a %s" % (_pct(compras / 100.0), nombre),
            "Su garante es además su proveedor principal. Si %s deja de venderle, "
            "el acreditado se queda sin operación Y sin garantía útil al mismo "
            "tiempo: es el mismo riesgo contado dos veces." % nombre,
            "concentración de proveedores de Syntage"))
    if ventas and ventas > 25:
        fuera.append(Senal(
            ALTA, "El %s de sus ventas son a %s" % (_pct(ventas / 100.0), nombre),
            "Sus ingresos dependen de la misma entidad que garantiza el crédito.",
            "concentración de clientes de Syntage"))
    return fuera


# ─────────────────────────────────────────────────────────────────────────────
def senales(datos):
    """Todas las señales derivadas, ordenadas por peso.

    `datos` es lo que devuelve `reunir()`.
    """
    fuera = []
    fuera += _senales_fiscales(datos.get("fiscal"))
    fuera += _senales_declaracion_vacia(datos.get("fiscal"))
    fuera += _senales_banderas(datos.get("perfil"))
    fuera += _senal_no_bancarizado(datos.get("perfil"), datos.get("cuentas_meta"),
                                   datos.get("cfdi"))
    fuera += _senal_cuentas_por_pagar(datos.get("cfdi"))
    fuera += _senal_sin_empleados(datos.get("perfil"))
    fuera += _senal_buro_sin_historial(datos.get("buro"))
    fuera += _senal_partes_relacionadas(datos.get("perfil"), datos.get("garante"))
    return sorted(fuera, key=lambda s: ORDEN[s.peso])


# ─────────────────────────────────────────────────────────────────────────────
# Reunir
# ─────────────────────────────────────────────────────────────────────────────
def reunir(folio, sb=None):
    """Todo lo que el resumen necesita, de un solo viaje a la base."""
    import db
    import insumos_riesgo
    sb = sb or db.cliente()

    exp = sb.table("expedientes").select("*").eq("folio", folio).execute().data
    if not exp:
        raise ValueError("No existe el expediente %s" % folio)
    exp = exp[0]

    ins = insumos_riesgo.reunir(folio, sb)
    evals = sb.table("evaluaciones_riesgo").select("*").eq("folio", folio) \
              .order("fecha", desc=True).execute().data or []
    fiscal = sb.table("info_fiscal").select("*").eq("folio", folio) \
               .order("ejercicio", desc=True).execute().data or []
    edos = sb.table("estados_cuenta").select("*").eq("folio", folio) \
             .order("fecha_final").execute().data or []
    cob = sb.table("cobertura_riesgo").select("*").eq("folio", folio).execute().data
    perfil = sb.table("perfil_empresa").select("*").eq("folio", folio).execute().data

    # El garante: si tiene folio propio se trae su evaluación, porque la pregunta
    # "¿aguantaría la garantía?" no se contesta con el score del acreditado.
    garante = (ins["expediente"].get("obligado_solidario") or {})
    garante_eval = None
    if garante.get("rfc"):
        otro = sb.table("expedientes").select("folio,razon_social") \
                 .eq("rfc", garante["rfc"]).execute().data
        if otro:
            ge = sb.table("evaluaciones_riesgo").select("*") \
                   .eq("folio", otro[0]["folio"]).order("fecha", desc=True) \
                   .limit(1).execute().data
            if ge:
                garante_eval = dict(ge[0], folio=otro[0]["folio"],
                                    razon_social=otro[0]["razon_social"])

    depositos = [e.get("monto_depositos") for e in edos if e.get("monto_depositos")]
    promedios = [e["saldo_promedio"] for e in edos if e.get("saldo_promedio") is not None]
    return {
        "folio": folio,
        "expediente": exp,
        "datos": ins["expediente"],
        "perfil": (perfil[0] if perfil else {}),
        "buro": ins["buro"],
        "cfdi": (ins["procedencia"].get("cfdi") or {}),
        "procedencia": ins["procedencia"],
        "evaluacion": (evals[0] if evals else None),
        "evaluaciones": evals,
        "fiscal": fiscal,
        "estados_cuenta": edos,
        "cuentas_meta": {
            "periodos": len(edos),
            "depositos_mensuales": (sum(depositos) / len(depositos)) if depositos else None,
            "saldo_promedio": (sum(promedios) / len(promedios)) if promedios else None,
        },
        "cobertura": (cob[0] if cob else {}),
        "garante": garante,
        "garante_evaluacion": garante_eval,
    }


# ─────────────────────────────────────────────────────────────────────────────
# El texto
# ─────────────────────────────────────────────────────────────────────────────
def _envolver(t, ancho):
    """Corta un texto en renglones sin partir palabras."""
    palabras, renglones, actual = str(t or "").split(), [], ""
    for p in palabras:
        if len(actual) + len(p) + 1 > ancho:
            renglones.append(actual)
            actual = p
        else:
            actual = (actual + " " + p).strip()
    if actual:
        renglones.append(actual)
    return renglones or [""]


def _encabezado(d, L):
    val = (d["datos"].get("cliente") or {}).get("validado") or {}
    sol = (d["datos"].get("credito") or {}).get("solicitada") or {}
    razon = val.get("razon_social") or d["folio"]
    titulo = "RESUMEN EJECUTIVO - %s" % razon
    L.append(titulo)
    L.append("=" * len(titulo))
    L.append("")
    L.append("Folio             %s" % d["folio"])
    L.append("RFC               %s" % (val.get("rfc") or "-"))
    L.append("Actividad         %s" % (d["perfil"].get("actividad_principal") or "-"))
    L.append("Alta ante el SAT  %s" % (d["perfil"].get("fecha_constitucion") or "-"))
    empleados = d["perfil"].get("empleados")
    L.append("Empleados         %s" % (empleados if empleados is not None else "-"))
    L.append("Línea solicitada  %s, pago %s" % (_pesos(sol.get("linea")),
                                                (sol.get("plazo") or "-").lower()))
    L.append("")


def _bloque_modelo(d, L):
    ev, p = d["evaluacion"], d["procedencia"]
    L.append("EL MODELO")
    L.append("-" * 9)
    if not ev:
        L.append("No se ha corrido. Sin score no hay nada que contrastar:")
        L.append("    python nea.py riesgo %s" % d["folio"])
        L.append("")
        return

    L.append("Score %s  ->  %s" % (
        "-" if ev.get("score") is None else "%.4f" % float(ev["score"]),
        ev.get("veredicto")))
    L.append("Línea que propone el modelo: %s" % _pesos(ev.get("linea_propuesta")))
    L.append("")
    for etiqueta, campo in (("Perfil de empresa", "modulo_perfil"),
                            ("Buró de crédito", "modulo_buro"),
                            ("Estados de cuenta", "modulo_edos_cuenta"),
                            ("Declaración anual", "modulo_declaracion")):
        v = ev.get(campo)
        L.append("    %-21s %s" % (etiqueta + ":",
                                   "sin datos" if v is None else "%.4f" % float(v)))

    sin = ev.get("modulos_sin_datos") or []
    if sin:
        L.append("")
        for renglon in _envolver(
                "Este score se calculó sobre %d de los 4 módulos. Los pesos de los que "
                "faltan se repartieron entre los demás, así que el número no es "
                "comparable contra uno completo." % (4 - len(sin)), 74):
            L.append(renglon)
    if ev.get("compuerta_abierta") is False:
        L.append("")
        L.append("AVISO: se corrió con la compuerta de riesgo cerrada. No es dictaminable.")

    L.append("")
    L.append("Calculado con:")
    L.append("    Buró                %s (%s)" % (p.get("buro") or "-",
                                                  p.get("buro_resultado") or "sin consulta"))
    if p.get("fuente_ingresos") == "cfdi_anio_corriente":
        c = d["cfdi"]
        L.append("    Ingresos            CFDI de %s, no la declaración anual"
                 % c.get("ejercicio"))
        L.append("                        %s en %s meses, anualizado"
                 % (_pesos(c.get("ingresos_netos_acumulados")),
                    c.get("meses_transcurridos")))
        L.append("                        el último ejercicio declarado ya no describe")
        L.append("                        a esta empresa")
    else:
        L.append("    Ingresos            declaración anual %s"
                 % (p.get("ejercicio_fiscal") or "-"))
    L.append("    Estados de cuenta   %d periodo(s), saldo promedio %s"
             % (d["cuentas_meta"]["periodos"],
                _pesos(d["cuentas_meta"]["saldo_promedio"])))
    L.append("")


def _bloque_senales(d, L):
    ss = senales(d)
    L.append("LO QUE EL SCORE NO CAPTURA")
    L.append("-" * 26)
    if not ss:
        for renglon in _envolver(
                "Nada. Ninguna señal fuera del modelo, que es poco común y también es "
                "información.", 74):
            L.append(renglon)
        L.append("")
        return

    etiquetas = {ALTA: "MUEVEN LA DECISIÓN",
                 MEDIA: "HAY QUE CONSIDERARLAS",
                 BAJA: "PARA EL EXPEDIENTE"}
    for peso in (ALTA, MEDIA, BAJA):
        grupo = [s for s in ss if s.peso == peso]
        if not grupo:
            continue
        L.append("")
        L.append(etiquetas[peso])
        for s in grupo:
            L.append("")
            L.append("  - %s" % s.titulo)
            for renglon in _envolver(s.detalle, 70):
                L.append("    %s" % renglon)
            L.append("    fuente: %s" % s.fuente)
    L.append("")


def _bloque_garantia(d, L):
    g, ge = d["garante"], d["garante_evaluacion"]
    if not (g.get("razon_social") or ge):
        return
    L.append("LA GARANTÍA")
    L.append("-" * 11)
    L.append("Obligado solidario: %s" % (g.get("razon_social") or g.get("rfc") or "-"))
    if ge:
        L.append("Evaluado por su cuenta en %s:" % ge["folio"])
        L.append("    Score %s  ->  %s   (línea %s)" % (
            "-" if ge.get("score") is None else "%.4f" % float(ge["score"]),
            ge.get("veredicto"), _pesos(ge.get("linea_propuesta"))))
        sin = ge.get("modulos_sin_datos") or []
        if sin:
            L.append("    sobre %d de 4 módulos" % (4 - len(sin)))
        L.append("")
        for renglon in _envolver(
                "Que el garante califique mejor que el acreditado no cierra la pregunta: "
                "hay que ver si su propio expediente trae señales, y si el control de las "
                "dos está en las mismas manos.", 74):
            L.append(renglon)
    else:
        for renglon in _envolver(
                "No se ha evaluado por su cuenta. Una garantía sin score es una firma, no "
                "una cobertura: conviene abrirle folio propio y correr el modelo con la "
                "misma línea.", 74):
            L.append(renglon)
    L.append("")


def _bloque_observaciones(d, L):
    obs = [o for o in (d["datos"].get("observaciones") or [])
           if o.get("estado") == "abierta"]
    graves = [o for o in obs if o.get("severidad") in ("alta", "intermedia")]
    L.append("OBSERVACIONES ABIERTAS DE LA REVISIÓN")
    L.append("-" * 37)
    L.append("%d abiertas, %d de gravedad alta o intermedia." % (len(obs), len(graves)))
    if graves:
        L.append("")
        for o in graves[:12]:
            titulo = (o.get("descripcion") or "").split(" - ")[0].split(" — ")[0]
            if len(titulo) > 66:
                titulo = _envolver(titulo, 63)[0] + "..."
            L.append("  [%-4s] %s" % ((o.get("severidad") or "?")[:4], titulo))
        if len(graves) > 12:
            L.append("  ... y %d más:  python nea.py estado %s"
                     % (len(graves) - 12, d["folio"]))
    L.append("")

    pendientes = list(dict.fromkeys(o["pedir"] for o in obs if o.get("pedir")))
    if pendientes:
        L.append("PENDIENTE DEL CLIENTE")
        L.append("-" * 21)
        for i, p in enumerate(pendientes, 1):
            for j, renglon in enumerate(_envolver(p, 72)):
                L.append("  %s%s" % ("%d. " % i if j == 0 else "   ", renglon))
        L.append("")


def texto(d):
    """El resumen ejecutivo, listo para leer o pegar en un correo.

    Cierra sin recomendación a propósito. La tentación de terminar con "se
    recomienda aprobar" es fuerte y está mal: el resumen que decide por el
    comité deja de ser un resumen.
    """
    L = []
    _encabezado(d, L)
    _bloque_modelo(d, L)
    _bloque_senales(d, L)
    _bloque_garantia(d, L)
    _bloque_observaciones(d, L)
    L.append("Generado el %s. Sin recomendación: los hechos van ordenados por peso"
             % date.today().isoformat())
    L.append("y la decisión la firma el comité.")
    return "\n".join(L)
