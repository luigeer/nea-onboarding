# -*- coding: utf-8 -*-
"""
front.py — El tablero, en el navegador
=======================================
Se abre con `python nea.py front`. No hay que saber la terminal más allá de eso.

**Por qué Streamlit y no una aplicación web de verdad.** Este front *llama* al
validador, al modelo de riesgo y al resumen ejecutivo; no los reimplementa. Un
front en otro lenguaje tendría que copiar las compuertas —qué falta para pasar a
riesgo, qué falta para generar, cuándo un riesgo alto se puede asumir— y dos
copias de una regla de negocio se separan siempre. La que se separa en silencio
es la que autoriza créditos.

**Lo que este front deliberadamente NO hace: autorizar.** Se puede ver todo y no
se puede aprobar nada. Autorizar una línea exige, por cada riesgo que se asume,
una justificación escrita y el nombre de quien la firma; un botón "Aprobar" en
una pantalla convierte eso en un clic el primer día que haya prisa. Cuando se
agregue, tiene que pedir la justificación antes de dejar avanzar, no después.
"""

import os
import sys

import streamlit as st

RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

# El sidebar abierto por defecto: navegar entre clientes es lo principal de esta
# pantalla, y colapsado obliga a descubrir un boton para hacer lo mas comun.
st.set_page_config(page_title="Onboarding Nea", page_icon="◆", layout="wide",
                   initial_sidebar_state="expanded")

CORAL = "#F1654B"

VEREDICTO_COLOR = {"Aprobado": "#1B8A5A", "Comité": "#B8860B",
                   "Rechazado": "#C1372B", "Sin datos suficientes": "#777777"}

# Los mismos umbrales que usa el tablero de la terminal. Se importan en vez de
# repetirse: si mañana cambian, cambian en un solo lugar.
try:
    from nea import DIAS_ATORADO, ETAPAS, _bloqueo
except Exception:                                   # pragma: no cover
    DIAS_ATORADO, ETAPAS, _bloqueo = {}, [], None


# ─────────────────────────────────────────────────────────────────────────────
# Datos
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _tablero():
    import db
    return db.cliente().table("tablero").select("*").execute().data or []


@st.cache_data(ttl=60)
def _coberturas():
    import db
    filas = db.cliente().table("cobertura_riesgo").select("*").execute().data or []
    return {c["folio"]: c for c in filas}


@st.cache_data(ttl=60)
def _expediente(folio):
    import db
    return db.cargar(folio)


@st.cache_data(ttl=60)
def _perfil(folio):
    import db
    filas = db.cliente().table("perfil_empresa").select("*") \
              .eq("folio", folio).execute().data
    return filas[0] if filas else {}


@st.cache_data(ttl=60)
def _evaluaciones(folio):
    import db
    return db.cliente().table("evaluaciones_riesgo").select("*") \
             .eq("folio", folio).order("fecha", desc=True).execute().data or []


@st.cache_data(ttl=60)
def _bitacora(folio):
    import db
    return db.cliente().table("bitacora_etapas").select("*") \
             .eq("folio", folio).order("entro_el").execute().data or []


@st.cache_data(ttl=60)
def _estados_cuenta(folio):
    import db
    return db.cliente().table("estados_cuenta").select("*") \
             .eq("folio", folio).order("fecha_final").execute().data or []


@st.cache_data(ttl=60)
def _fiscal(folio):
    import db
    return db.cliente().table("info_fiscal").select("*") \
             .eq("folio", folio).order("ejercicio", desc=True).execute().data or []


def _pesos(v):
    try:
        return "$%s" % format(float(v), ",.2f")
    except (TypeError, ValueError):
        return "—"


def _bloqueo_de(folio, fila, cobs):
    """El bloqueo real, calculado por el mismo código que el tablero."""
    if _bloqueo is None:
        return ""
    try:
        return _bloqueo(_expediente(folio), fila, cobs.get(folio)) or ""
    except Exception as e:
        return "no se pudo evaluar: %s" % str(e)[:60]


# ─────────────────────────────────────────────────────────────────────────────
# Tablero
# ─────────────────────────────────────────────────────────────────────────────
def vista_tablero(filas, cobs):
    st.markdown("### Tablero")

    total = len(filas)
    en_firma = sum(1 for f in filas if f.get("etapa") == "firma")
    atorados = [f for f in filas
                if (f.get("dias_en_etapa") or 0) >= DIAS_ATORADO.get(f.get("etapa"), 99)]
    pendientes = sum(f.get("pendientes_cliente") or 0 for f in filas)
    autorizado = sum(float(f.get("linea_autorizada") or 0) for f in filas)

    c = st.columns(5)
    c[0].metric("Expedientes", total)
    c[1].metric("Atorados", len(atorados),
                help="Llevan más días de lo normal en su etapa")
    c[2].metric("En firma", en_firma)
    c[3].metric("Pendientes del cliente", pendientes)
    c[4].metric("Línea autorizada", _pesos(autorizado))

    orden = {e: i for i, e in enumerate(ETAPAS)}
    filas = sorted(filas, key=lambda f: (orden.get(f.get("etapa"), 99),
                                         -(f.get("dias_en_etapa") or 0)))
    st.write("")
    for f in filas:
        dias = f.get("dias_en_etapa") or 0
        atorado = dias >= DIAS_ATORADO.get(f.get("etapa"), 99)
        bloqueo = _bloqueo_de(f["folio"], f, cobs)
        score = f.get("score")
        color = VEREDICTO_COLOR.get(f.get("veredicto"), "#777777")

        col = st.columns([2, 4, 2, 1.4, 2, 5])
        col[0].markdown("**%s**" % f["folio"])
        col[1].write((f.get("razon_social") or "")[:44])
        col[2].write(f.get("etapa") or "—")
        col[3].markdown(("<span style='color:%s'>%s%d d</span>"
                         % (CORAL if atorado else "inherit",
                            "⚠ " if atorado else "", dias)),
                        unsafe_allow_html=True)
        if score is None:
            col[4].write("sin evaluar")
        else:
            col[4].markdown("<span style='color:%s'><b>%.4f</b> %s</span>"
                            % (color, float(score), f.get("veredicto") or ""),
                            unsafe_allow_html=True)
        col[5].write(bloqueo or "—")
        st.divider()

    if atorados:
        st.warning("Atorados: " + ", ".join(
            "%s (%d d en %s)" % (f["folio"], f.get("dias_en_etapa") or 0, f.get("etapa"))
            for f in atorados))


# ─────────────────────────────────────────────────────────────────────────────
# Un cliente
# ─────────────────────────────────────────────────────────────────────────────
def vista_cliente(folio, filas, cobs):
    fila = next((f for f in filas if f["folio"] == folio), {})
    exp = _expediente(folio)
    val = (exp.get("cliente") or {}).get("validado") or {}

    st.markdown("### %s" % (val.get("razon_social") or folio))
    c = st.columns(4)
    c[0].metric("Folio", folio)
    c[1].metric("Etapa", fila.get("etapa") or "—")
    c[2].metric("Solicitada", _pesos(fila.get("linea_solicitada")))
    c[3].metric("Autorizada", _pesos(fila.get("linea_autorizada")))

    bloqueo = _bloqueo_de(folio, fila, cobs)
    if bloqueo:
        st.info("**Qué lo detiene:** %s" % bloqueo)

    tabs = st.tabs(["Score", "Perfil", "Observaciones", "Banco y fiscal",
                    "Documentos", "Historial", "Resumen ejecutivo",
                    "Alta en la base operativa", "Monedero"])

    with tabs[0]:
        _tab_score(folio)
    with tabs[1]:
        _tab_perfil(folio)
    with tabs[2]:
        _tab_observaciones(exp)
    with tabs[3]:
        _tab_banco_fiscal(folio)
    with tabs[4]:
        _tab_documentos(exp)
    with tabs[5]:
        _tab_historial(folio)
    with tabs[6]:
        _tab_resumen(folio)
    with tabs[7]:
        _tab_alta(folio, exp)
    with tabs[8]:
        _tab_monedero(folio, exp)


MODULOS = [("Perfil de empresa", "modulo_perfil", 0.20),
           ("Buró de crédito", "modulo_buro", 0.25),
           ("Estados de cuenta", "modulo_edos_cuenta", 0.275),
           ("Declaración anual", "modulo_declaracion", 0.275)]


def _tab_score(folio):
    evals = _evaluaciones(folio)
    if not evals:
        st.write("Todavía no se ha corrido el modelo.")
        return
    ev = evals[0]

    c = st.columns(3)
    score = ev.get("score")
    c[0].metric("Score", "—" if score is None else "%.4f" % float(score))
    c[1].metric("Veredicto", ev.get("veredicto") or "—")
    # El modelo guarda 0 cuando no aprueba, y "$0.00" junto a una línea
    # autorizada de $50,000 se lee como si hubiera propuesto cero pesos. No
    # propuso cero: no propuso nada, y la línea la puso el comité.
    propuesta = float(ev.get("linea_propuesta") or 0)
    c[2].metric("Línea que propone el modelo",
                _pesos(propuesta) if propuesta > 0 else "no propone")

    if ev.get("compuerta_abierta") is False:
        st.error("Este score se corrió con la compuerta de riesgo cerrada. "
                 "No es dictaminable.")
    sin = ev.get("modulos_sin_datos") or []
    if sin:
        st.warning(
            "Calculado sobre %d de los 4 módulos. Los pesos de los que faltan se "
            "repartieron entre los demás, así que **no es comparable** contra un "
            "score completo. Faltan: %s."
            % (4 - len(sin), ", ".join(s.replace("_", " ") for s in sin)))

    st.markdown("**Por módulo**")
    for etiqueta, campo, peso in MODULOS:
        v = ev.get(campo)
        col = st.columns([3, 1.2, 6])
        col[0].write(etiqueta)
        col[1].write("%.0f%%" % (peso * 100))
        if v is None:
            col[2].write("sin datos — sale del promedio")
        else:
            col[2].progress(min(1.0, max(0.0, float(v))), text="%.4f" % float(v))

    detalle = ev.get("detalle") or {}
    variables = detalle.get("variables") or {}
    if variables:
        with st.expander("Cada variable, con su peso dentro del módulo"):
            for mod, vs in variables.items():
                st.markdown("**%s**" % mod.replace("_", " "))
                for nombre, d in sorted(vs.items(), key=lambda x: -x[1]["peso"]):
                    p = d.get("puntaje")
                    st.write("· %-32s peso %.2f — %s"
                             % (nombre, d.get("peso", 0),
                                "sin datos" if p is None else "%.2f" % p))

    proc = (detalle.get("procedencia") or {})
    if proc:
        with st.expander("Con qué datos se calculó"):
            if proc.get("fuente_ingresos") == "cfdi_anio_corriente":
                cf = proc.get("cfdi") or {}
                st.write("Ingresos: **del CFDI de %s**, no de la declaración anual "
                         "— %s acumulados en %s meses, anualizado."
                         % (cf.get("ejercicio"),
                            _pesos(cf.get("ingresos_netos_acumulados")),
                            cf.get("meses_transcurridos")))
                if cf.get("cuentas_por_pagar"):
                    st.write("Cuentas por pagar pendientes: **%s**"
                             % _pesos(cf["cuentas_por_pagar"]))
            else:
                st.write("Ingresos: declaración anual %s"
                         % proc.get("ejercicio_fiscal"))
            st.write("Buró: %s (%s)" % (proc.get("buro") or "—",
                                        proc.get("buro_resultado") or "—"))
            st.write("Estados de cuenta: %s periodos en %s cuenta(s)"
                     % (proc.get("periodos_bancarios"), proc.get("cuentas_bancarias")))

    if len(evals) > 1:
        with st.expander("Evaluaciones anteriores (%d)" % (len(evals) - 1)):
            for e in evals[1:]:
                st.write("%s — %s %s (version %s)"
                         % ((e.get("fecha") or "")[:16],
                            "—" if e.get("score") is None else "%.4f" % float(e["score"]),
                            e.get("veredicto") or "", e.get("version_modelo") or ""))


def _tab_perfil(folio):
    p = _perfil(folio)
    if not p:
        st.write("El perfil no se ha derivado. Se corre con "
                 "`python nea.py perfil %s`." % folio)
        return

    st.markdown("**Derivado de Syntage** — no se captura a mano")
    c = st.columns(3)
    c[0].write("**Estado**  \n%s (%s)" % (p.get("estado_nombre") or "—",
                                          p.get("estado_codigo") or "—"))
    c[1].write("**Alta ante el SAT**  \n%s" % (p.get("fecha_constitucion") or "—"))
    c[2].write("**Empleados**  \n%s" % (p.get("empleados")
                                        if p.get("empleados") is not None else "—"))
    st.write("**Actividad**  \n%s" % (p.get("actividad_principal") or "—"))

    c = st.columns(3)
    c[0].write("**CFDI emitidos**  \n%s" % (p.get("cfdi_emitidos") or "—"))
    c[1].write("**Años con facturación**  \n%s" % (p.get("anios_con_facturacion") or "—"))
    c[2].write("**Facturado (%s)**  \n%s" % (p.get("ultimo_anio_facturado") or "—",
                                             _pesos(p.get("ingresos_cfdi"))))

    tc, tp = p.get("top_cliente") or {}, p.get("top_proveedor") or {}
    c = st.columns(2)
    c[0].write("**Cliente principal**  \n%s — %s%%"
               % (tc.get("nombre") or "—", tc.get("share")))
    c[1].write("**Proveedor principal**  \n%s — %s%%"
               % (tp.get("nombre") or "—", tp.get("share")))
    if p.get("compras_partes_relacionadas"):
        st.warning("El **%s%%** de sus compras son a su propio obligado solidario."
                   % p["compras_partes_relacionadas"])

    rojas = p.get("banderas_rojas") or []
    if rojas:
        st.error("**%d bandera(s) de riesgo en rojo:** %s" % (len(rojas), ", ".join(rojas)))
    else:
        st.success("Ninguna bandera de riesgo en rojo.")

    st.markdown("**Captura del operador**")
    c = st.columns(3)
    c[0].write("**Giro**  \n%s%s" % (p.get("giro_codigo") or "—",
                                     "" if p.get("giro_codigo") else
                                     " (sugerido: %s)" % p.get("giro_sugerido")))
    c[1].write("**Procedencia**  \n%s" % (p.get("procedencia_lead") or "—"))
    pd_ = p.get("presencia_digital") or {}
    c[2].write("**Dominio propio**  \n%s" % ("sí" if pd_.get("dominio_propio")
                                             else "no" if pd_.get("dominio_propio") is False
                                             else "sin verificar"))
    if pd_.get("nota"):
        st.caption(pd_["nota"])


SEV_COLOR = {"alta": "#C1372B", "intermedia": "#B8860B", "baja": "#777777"}


def _tab_observaciones(exp):
    obs = exp.get("observaciones") or []
    if not obs:
        st.write("Sin observaciones.")
        return

    estados = ["abierta", "aceptada", "resuelta"]
    elegidos = st.multiselect("Estado", estados, default=["abierta", "aceptada"])
    filtradas = [o for o in obs if o.get("estado") in elegidos]
    st.caption("%d de %d observaciones" % (len(filtradas), len(obs)))

    for o in sorted(filtradas, key=lambda x: {"alta": 0, "intermedia": 1}.get(
            x.get("severidad"), 2)):
        sev = o.get("severidad") or "?"
        desc = o.get("descripcion") or ""
        titulo = desc.split(" — ")[0]
        cuerpo = desc[len(titulo) + 3:] if " — " in desc else ""
        with st.expander("[%s · %s] %s" % (sev, o.get("estado"), titulo[:90])):
            if cuerpo:
                st.write(cuerpo)
            if o.get("pedir"):
                st.info("**Se le pide al cliente:** %s" % o["pedir"])
            if o.get("justificacion"):
                st.markdown("**Justificación de la aceptación**")
                st.write(o["justificacion"])
                st.caption("Firma: %s" % (o.get("aceptada_por") or "sin nombre"))
            if o.get("resuelta_por"):
                st.caption("Resuelta: %s" % o["resuelta_por"])


def _tab_banco_fiscal(folio):
    edos = _estados_cuenta(folio)
    st.markdown("**Estados de cuenta**")
    if not edos:
        st.write("Ninguno cargado.")
    else:
        import pandas as pd
        df = pd.DataFrame([{
            "Corte": e.get("fecha_final"), "Banco": e.get("banco"),
            "Saldo promedio": e.get("saldo_promedio"),
            "Mínimo": e.get("saldo_minimo"), "Máximo": e.get("saldo_maximo"),
            "Depósitos": e.get("monto_depositos"),
            "Retiros": e.get("monto_retiros"),
            "N° dep.": e.get("numero_depositos"),
        } for e in edos])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.line_chart(df.set_index("Corte")[["Saldo promedio"]])

    st.markdown("**Declaraciones anuales**")
    fis = _fiscal(folio)
    if not fis:
        st.write("Ninguna proyectada.")
        return
    import pandas as pd
    df = pd.DataFrame([{
        "Ejercicio": f.get("ejercicio"), "Declarado": f.get("declarado"),
        "Ingresos": f.get("ingresos_totales"),
        "Utilidad op.": f.get("utilidad_operacion"),
        "Activo CP": f.get("activo_corto_plazo"),
        "Pasivo CP": f.get("pasivo_corto_plazo"),
        "Capital contable": f.get("capital_contable"),
    } for f in fis])
    st.dataframe(df, use_container_width=True, hide_index=True)
    negativos = [f for f in fis if (f.get("capital_contable") or 0) < 0]
    if negativos:
        st.error("Capital contable **negativo** en %s. Las pérdidas acumuladas "
                 "superan el capital aportado."
                 % ", ".join(str(f["ejercicio"]) for f in negativos))


def _tab_documentos(exp):
    docs = [d for d in (exp.get("documentos") or []) if not d.get("superado_por")]
    if not docs:
        st.write("Sin documentos registrados.")
        return
    import pandas as pd
    df = pd.DataFrame([{
        "Tipo": d.get("tipo"), "Sujeto": d.get("sujeto") or "",
        "Emitida": d.get("fecha_emision") or "", "Vence": d.get("vigente_hasta") or "",
        "Corte": d.get("corte") or "", "Legible": d.get("legible"),
    } for d in docs])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _tab_historial(folio):
    bit = _bitacora(folio)
    if not bit:
        st.write("Sin bitácora.")
        return
    from datetime import datetime, timezone

    def cuando(s):
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))

    for i, b in enumerate(bit):
        ini = cuando(b["entro_el"])
        fin = (cuando(bit[i + 1]["entro_el"]) if i + 1 < len(bit)
               else datetime.now(timezone.utc))
        dias = (fin - ini).days
        actual = " · **actual**" if i + 1 == len(bit) else ""
        st.write("**%s** — entró el %s, %d día(s)%s"
                 % (b["etapa_a"], ini.strftime("%Y-%m-%d %H:%M"), dias, actual))
    st.caption("La bitácora arranca cuando se instaló: lo anterior no tiene "
               "historia real.")


def _tab_resumen(folio):
    ruta = os.path.join(RAIZ, "out", "%s_resumen_ejecutivo.txt" % folio)
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as fh:
            st.code(fh.read(), language=None)
        st.caption("Generado con `python nea.py resumen %s`" % folio)
        return
    if st.button("Generar el resumen ejecutivo ahora"):
        try:
            import resumen_ejecutivo
            st.code(resumen_ejecutivo.texto(resumen_ejecutivo.reunir(folio)),
                    language=None)
        except Exception as e:
            st.error("No se pudo: %s" % e)


# ─────────────────────────────────────────────────────────────────────────────
# Alta manual en el Django operativo
#
# Cada valor va en su propio `st.code`: ese widget trae botón de copiar, que es
# justo lo que se necesita para llenar un formulario campo por campo. Un
# dataframe se ve mejor y no se puede copiar celda por celda.
# ─────────────────────────────────────────────────────────────────────────────
def _tab_alta(folio, exp):
    import alta_django as ad

    p = _perfil(folio)
    if p:
        exp = dict(exp, _perfil=p)

    st.markdown("#### Alta en la base operativa")
    st.caption("Los campos del formulario de Django, en el orden de la pantalla y "
               "con el formato que espera. Las fechas ya vienen en aaaa-mm-dd.")

    avisos = ad.pendientes(exp)
    if avisos:
        with st.expander("⚠ %d cosa(s) por resolver antes o durante el alta"
                         % len(avisos), expanded=True):
            for a in avisos:
                st.markdown("- %s" % a)

    for s in ad.secciones(exp):
        st.divider()
        if s.get("titulo"):
            st.markdown("**%s**" % s["titulo"])
        st.markdown("###### %s" % s["seccion"])
        for c in s["campos"]:
            col = st.columns([2, 3])
            col[0].markdown("%s:" % c["etiqueta"])
            with col[1]:
                if c["tipo"] == "sistema":
                    st.caption(c["valor"])
                elif c["tipo"] == "checkbox":
                    st.markdown("**%s**" % ("☑ marcar" if c["valor"]
                                            else "☐ dejar sin marcar"))
                elif c["tipo"] == "casillas":
                    for v in ad.VINCULOS:
                        st.markdown("%s %s" % ("☑" if v in (c["valor"] or []) else "☐", v))
                elif c["valor"] in (None, "", []):
                    st.markdown(":gray[— vacío a propósito —]" if c.get("opcional")
                                else ":red[FALTA]")
                else:
                    st.code(str(c["valor"]), language=None)
                if c["nota"]:
                    st.caption(c["nota"])

    st.divider()
    with st.expander("Todo en texto plano"):
        st.code(ad.texto(exp), language=None)


# ─────────────────────────────────────────────────────────────────────────────
# Monedero — adopción, estaciones y comisión del monedero de combustible
# actual del cliente. A diferencia del resto de este front, SÍ escribe a
# disco (out/{folio}_monedero.json): la descarga manual entre las dos
# etapas puede tardar días, y st.session_state no sobrevive a que el
# operador cierre el navegador. Ver spec en
# docs/superpowers/specs/2026-08-20-monedero-seccion-cliente-design.md.
# ─────────────────────────────────────────────────────────────────────────────
def _tab_monedero(folio, exp):
    import estaciones_monedero as em
    import monederos

    st.caption("Informativo — no bloquea el avance del expediente. Solo tiene "
               "sentido correrlo mientras el cliente está en onboarding activo.")

    revision = em.cargar_revision(folio)

    if st.button("Revisar monedero" if revision is None else "Volver a revisar monedero"):
        with st.spinner("Consultando Syntage..."):
            try:
                em.revisar_cliente(folio)
            except Exception as e:
                st.error("No se pudo: %s" % e)
                return
        st.rerun()

    if revision is None:
        st.write("Todavía no se ha revisado. El botón de arriba consulta "
                 "Syntage (sin descargar nada) y dice si el cliente usa un "
                 "monedero real, y cuánto le cobra de comisión.")
        return

    if not revision["monederos"]:
        st.info("No se detectó monedero real en los últimos meses. (%s)"
                 % revision["estado"])
        return

    rfc_cliente = monederos._rfc_de_expediente(exp)
    for m in revision["monederos"]:
        st.markdown("#### %s (%s)" % (m["nombre_comercial"], m["rfc_monedero"]))
        if not m["es_real"]:
            st.write("No confirmó el patrón de monedero real — parece compra "
                     "directa en una gasolinera que también tiene monedero de marca.")
            continue

        if m["comision"]:
            for mes, c in sorted(m["comision"].items()):
                st.write("**Comisión %s:** $%s" % (mes, format(c["monto"], ",.2f")))

        st.write("**Qué descargar del panel de Syntage:**")
        import pandas as pd
        st.dataframe(pd.DataFrame([{
            "Mes": p["mes"], "Archivo esperado": p["archivo_esperado"],
            "Folio fiscal": p["folio_fiscal"],
        } for p in m["plan_descarga"]]), use_container_width=True, hide_index=True)

        _tab_monedero_reporte(folio, rfc_cliente, m, revision)


def _tab_monedero_reporte(folio, rfc_cliente, m, revision):
    import estaciones_monedero as em
    import estado_cuenta_monedero as ecm

    if st.button("Leer descargas", key="leer_%s_%s" % (folio, m["rfc_monedero"])):
        with st.spinner("Leyendo los PDF/XML descargados..."):
            try:
                reporte = ecm.reporte_cliente(rfc_cliente)
                revision = em.actualizar_con_reporte(revision, reporte)
                em.guardar_revision(folio, revision)
            except Exception as e:
                st.error("No se pudo: %s" % e)
                return
        st.rerun()

    if not m["reporte"]:
        st.caption("Todavía no se han leído descargas para este monedero.")
        return

    import pandas as pd
    filas_mes, filas_estacion = [], []
    for mes, d in sorted(m["reporte"].items()):
        pct = d["porcentaje_comision"]
        filas_mes.append({
            "Mes": mes, "Total facturado": d["total_facturado"],
            "% comisión": ("%.2f%%" % (pct * 100)) if pct is not None
                          else "falta subir el complemento de este mes",
        })
        for e in d["por_estacion"]:
            filas_estacion.append({"Mes": mes, "RFC estación": e["rfc_estacion"],
                                    "Clave": e["clave_estacion"], "Cargas": e["cargas"],
                                    "Litros": e["litros"], "Importe": e["importe"]})

    st.write("**Por mes:**")
    st.dataframe(pd.DataFrame(filas_mes), use_container_width=True, hide_index=True)

    if filas_estacion:
        estaciones_distintas = {(f["RFC estación"], f["Clave"]) for f in filas_estacion}
        st.write("**Por estación** (%d distinta(s) en los meses leídos):" % len(estaciones_distintas))
        st.dataframe(pd.DataFrame(filas_estacion), use_container_width=True, hide_index=True)

    if m["sospechosos"]:
        with st.expander("⚠ %d archivo(s) sospechoso(s) — no cuadraron o no se pudieron usar"
                         % len(m["sospechosos"])):
            for s in m["sospechosos"]:
                st.write(s)


# ─────────────────────────────────────────────────────────────────────────────
def main():
    st.markdown("<h2 style='margin-bottom:0'>Onboarding "
                "<span style='color:%s'>Nea</span></h2>" % CORAL,
                unsafe_allow_html=True)

    try:
        filas = _tablero()
        cobs = _coberturas()
    except Exception as e:
        st.error("No se pudo leer Supabase: %s" % e)
        st.caption("Revisa la conexión con `python db.py probar`.")
        return

    if not filas:
        st.info("No hay expedientes todavía. El primero se abre con "
                "`python nea.py nuevo ruta\\de\\la\\csf.pdf`.")
        return

    with st.sidebar:
        st.markdown("### Ver")
        opciones = ["Tablero"] + ["%s — %s" % (f["folio"],
                                               (f.get("razon_social") or "")[:26])
                                  for f in sorted(filas, key=lambda x: x["folio"])]
        elegido = st.radio("Expediente", opciones, label_visibility="collapsed")
        st.divider()
        if st.button("Recargar datos"):
            st.cache_data.clear()
            st.rerun()
        st.caption("Los datos se refrescan solos cada minuto.")
        st.divider()
        st.caption("Este tablero **no autoriza**. Autorizar una línea exige una "
                   "justificación escrita por cada riesgo que se asume y el "
                   "nombre de quien la firma; eso pasa por el expediente, no por "
                   "un botón.")

    if elegido == "Tablero":
        vista_tablero(filas, cobs)
    else:
        vista_cliente(elegido.split(" — ")[0], filas, cobs)


main()
