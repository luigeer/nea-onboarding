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

import tema

tema.aplicar(st)

CORAL = tema.ACENTO

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
    st.markdown("## Tablero")
    st.caption("Los expedientes reales están a medias: módulos sin datos y "
               "observaciones abiertas son el estado normal, no el caso de error.")

    total = len(filas)
    en_firma = sum(1 for f in filas if f.get("etapa") == "firma")
    atorados = [f for f in filas
                if (f.get("dias_en_etapa") or 0) >= DIAS_ATORADO.get(f.get("etapa"), 99)]
    pendientes = sum(f.get("pendientes_cliente") or 0 for f in filas)
    autorizado = sum(float(f.get("linea_autorizada") or 0) for f in filas)

    tema.html(st, tema.metricas([
        tema.metrica("Expedientes", total, "en proceso"),
        tema.metrica("Atorados", len(atorados), "pasaron el umbral de su etapa",
                     alerta=bool(atorados)),
        tema.metrica("En firma", en_firma,
                     ", ".join(f["folio"] for f in filas
                               if f.get("etapa") == "firma") or None),
        tema.metrica("Pendientes del cliente", pendientes, "documentos por recibir"),
        tema.metrica("Línea autorizada", _pesos(autorizado), "autorizada por comité"),
    ]))

    orden = {e: i for i, e in enumerate(ETAPAS)}
    filas = sorted(filas, key=lambda f: (orden.get(f.get("etapa"), 99),
                                         -(f.get("dias_en_etapa") or 0)))
    st.write("")
    st.markdown("### Expedientes")
    st.caption("Orden del flujo: " + " → ".join(tema.ETAPA_NOMBRE.get(e, e)
                                                for e in tema.ETAPAS))
    tema.html(st, tema.tabla_expedientes([
        tema.fila_expediente(
            f, _bloqueo_de(f["folio"], f, cobs),
            (f.get("dias_en_etapa") or 0) >= DIAS_ATORADO.get(f.get("etapa"), 99))
        for f in filas]))

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

    st.markdown("## %s" % (val.get("razon_social") or folio))

    # El flujo va arriba y siempre visible: "¿en qué paso voy?" es la pregunta
    # que hoy obliga a entrar a una pestaña.
    dias_etapa = fila.get("dias_en_etapa") or 0
    atorado = dias_etapa >= DIAS_ATORADO.get(fila.get("etapa"), 99)
    tema.html(st, tema.flujo_etapas(fila.get("etapa")) +
              '<div class="neaop-row" style="margin-top:10px">%s%s</div>'
              % (tema.chip_etapa(fila.get("etapa"), atorado),
                 tema.dias(dias_etapa, atorado)))

    abiertas = [o for o in (exp.get("observaciones") or [])
                if o.get("estado") == "abierta"]
    graves = [o for o in abiertas if o.get("severidad") in ("alta", "intermedia")]
    tema.html(st, tema.metricas([
        tema.metrica("Folio", folio),
        tema.metrica("Solicitada", _pesos(fila.get("linea_solicitada"))),
        tema.metrica("Autorizada", _pesos(fila.get("linea_autorizada")),
                     "por comité" if fila.get("linea_autorizada") else "sin autorizar",
                     ausente=not fila.get("linea_autorizada")),
        tema.metrica("Observaciones abiertas", len(abiertas),
                     "%d alta(s) o intermedia(s)" % len(graves),
                     alerta=bool(graves)),
        tema.metrica("Pendientes del cliente", fila.get("pendientes_cliente") or 0,
                     "documentos por recibir"),
    ]))

    bloqueo = _bloqueo_de(folio, fila, cobs)
    if bloqueo:
        tema.html(st, tema.bloque_detiene(bloqueo))

    # El separador "│" agrupa lo que es expediente de lo que son entregables.
    tabs = st.tabs(["Score", "Perfil", "Observaciones", "Banco y fiscal",
                    "Documentos", "Historial",
                    "│  Resumen ejecutivo", "Alta en la base operativa"])

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

    tema.html(st, tema.score_titular(ev.get("score"), ev.get("veredicto"),
                                     ev.get("linea_propuesta")))

    if ev.get("compuerta_abierta") is False:
        st.error("Este score se corrió con la compuerta de riesgo cerrada. "
                 "No es dictaminable.")
    sin = ev.get("modulos_sin_datos") or []
    if sin:
        tema.html(st, tema.salvedad(sin))

    st.write("")
    st.markdown("##### Por módulo")
    tema.html(st, "".join(tema.modulo(etiqueta, peso, ev.get(campo))
                          for etiqueta, campo, peso in MODULOS))

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


def _tab_observaciones(exp):
    """Todas las observaciones, ordenadas y abiertas.

    Antes había un filtro por estado con las resueltas apagadas por default.
    Filtrar obliga a decidir qué leer **antes** de leer, y lo que quedaba fuera
    era justo lo que explica por qué el expediente está como está. Ahora se
    ordenan —grave primero, y dentro de cada gravedad las abiertas antes que las
    aceptadas— y se ven todas. Ordenar no esconde; filtrar sí.
    """
    obs = exp.get("observaciones") or []
    if not obs:
        st.write("Sin observaciones.")
        return

    peso_sev = {"alta": 0, "intermedia": 1, "baja": 2}
    peso_est = {"abierta": 0, "aceptada": 1, "resuelta": 2}
    ordenadas = sorted(obs, key=lambda o: (peso_sev.get(o.get("severidad"), 3),
                                           peso_est.get(o.get("estado"), 3)))

    cuenta = {}
    for o in obs:
        cuenta[o.get("estado")] = cuenta.get(o.get("estado"), 0) + 1
    st.caption("%d observaciones · %s" % (
        len(obs), " · ".join("%d %s" % (n, e) for e, n in sorted(cuenta.items(),
                                                                 key=lambda x: str(x[0])))))

    tema.html(st, "".join(tema.observacion(o) for o in ordenadas))


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
            # Como documento y no como bloque de código: es lo que lee el comité.
            # Ni una palabra del texto generado se edita ni se resume.
            tema.html(st, tema.documento(fh.read()))
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
        st.write("")
        if s.get("titulo"):
            st.markdown("##### %s" % s["titulo"])
        st.markdown("**%s**" % s["seccion"])
        # Las casillas de vínculos se dibujan completas —marcadas y sin marcar—
        # porque el formulario del Django las muestra todas y hay que ver cuáles
        # NO van.
        marcado = []
        for c in s["campos"]:
            if c["tipo"] == "casillas":
                c = dict(c, valor=" ".join(
                    "%s %s" % ("☑" if v in (c["valor"] or []) else "☐", v)
                    for v in ad.VINCULOS))
            marcado.append(tema.campo(c))
        tema.html(st, '<div class="neaop-card neaop-pad">%s</div>' % "".join(marcado))
        # Los valores copiables van aparte: st.code trae el botón de copiar, que
        # es el punto de esta pestaña y que el HTML inyectado no puede dar.
        with st.expander("Copiar los valores de «%s»" % s["seccion"]):
            for c in s["campos"]:
                if c["tipo"] in ("sistema", "checkbox", "casillas"):
                    continue
                if c["valor"] in (None, "", []):
                    continue
                st.caption(c["etiqueta"])
                st.code(str(c["valor"]), language=None)

    st.write("")
    with st.expander("Todo en texto plano"):
        st.code(ad.texto(exp), language=None)


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
