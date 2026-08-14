# -*- coding: utf-8 -*-
"""
tema.py — El sistema de diseño de Nea, aplicado al front
=========================================================
El CSS vive en `assets/diseno/onboarding.css` tal como lo entregó el sistema de
diseño; aquí **no se reescribe**, se carga. Ese archivo se puede volver a
importar cuando el sistema cambie y esto sigue funcionando: lo único que este
módulo hace es armar el HTML de cada componente con las clases que ese CSS ya
define.

**Por qué componentes en HTML y no los widgets de Streamlit.** Los widgets de
Streamlit no distinguen las cosas que este producto necesita distinguir. Un
`st.metric` no sabe la diferencia entre "no propone" y "$0.00"; un
`st.progress` no sabe dibujar "sin datos" sin dibujar un cero. La regla del
negocio —la ausencia de un dato no es un dato desfavorable— se vuelve un
problema de pintura, y con los widgets de caja no se resuelve.

**Lo que sí se deja en Streamlit:** la navegación, las pestañas, las tablas de
datos y las gráficas. Ahí Streamlit hace bien su trabajo y solo se le cambia el
color con CSS.

**El escapado no es opcional.** Todo lo que entra a estas funciones sale del
expediente, y una justificación de riesgo la escribe una persona. `esc()` se
aplica a cada dato, siempre. Un `<` en una justificación no puede romper la
pantalla ni ejecutarse.
"""

import os
import re

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSS = os.path.join(RAIZ, "assets", "diseno", "onboarding.css")

# Las etapas se IMPORTAN, no se copian. Ya pasó: aquí había una lista escrita a
# mano y un expediente guardado como "firmado" en vez de "firma" no coincidía con
# ninguna, así que el flujo se dibujaba sin marcar la etapa actual y el chip
# decía "—". Callado, además: nada falla cuando un nombre no está en la lista.
from nea import ETAPAS  # noqa: E402  (el front ya depende de nea)

ETAPA_NOMBRE = {"apertura": "apertura", "validacion": "validación",
                "riesgo": "riesgo", "generacion": "generación",
                "firma": "firma", "cerrado": "cerrado"}

# Cada estado se codifica tres veces —color, glifo y trazo del borde— para que
# se distinga en escala de grises y con daltonismo. El color solo no alcanza:
# el rojo y el verde son justo el par que más gente confunde.
GLIFO_VEREDICTO = {"Aprobado": "✓", "Comité": "◑", "Rechazado": "✕",
                   "Sin datos suficientes": "⌀", None: "○"}
CLASE_VEREDICTO = {"Aprobado": "aprobado", "Comité": "comite",
                   "Rechazado": "rechazado",
                   "Sin datos suficientes": "sindatos", None: "sinevaluar"}
GLIFO_SEVERIDAD = {"alta": "▲", "intermedia": "◆", "baja": "●"}
GLIFO_ESTADO = {"abierta": "○", "aceptada": "◑", "resuelta": "✓"}

# El acento del manual de marca (PANTONE 172, muestreado del logotipo). El CSS
# del sistema trae #F1654B, que fue el que yo puse en el front original; esta
# capa lo alinea con la marca sin tocar el archivo importado.
ACENTO = "#FF664C"
ACENTO_HOVER = "#E5533C"
ACENTO_SUAVE = "#FFEDE9"
ACENTO_TINTA = "#C1442F"


def esc(t):
    """Escapa un dato del expediente para meterlo en HTML.

    Los saltos de línea se conservan como `<br>` porque las justificaciones y
    las descripciones vienen en párrafos: aplanarlas a un renglón las vuelve
    ilegibles, y son documentos legales.
    """
    if t is None:
        return ""
    s = str(t)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    return s.replace("\n", "<br>")


def _con_enlaces(t):
    """Escapa el texto y convierte las URL en enlaces que se puedan abrir.

    Los campos de archivo del alta traen la liga del documento en Drive. Como
    texto plano no sirven de nada: el punto de tenerlas es abrir el papel y
    subirlo. Se escapa primero y se enlaza después, para que un `<` en el texto
    siga sin poder inyectar marcado.
    """
    escapado = esc(t)
    return re.sub(r"(https://[^\s<]+)",
                  r'<a href="\1" target="_blank" rel="noopener">abrir en Drive ↗</a>',
                  escapado)


def pesos(v):
    try:
        return "$%s" % format(float(v), ",.2f")
    except (TypeError, ValueError):
        return "—"


# ─────────────────────────────────────────────────────────────────────────────
# La hoja de estilo
# ─────────────────────────────────────────────────────────────────────────────
def compactar(hoja):
    """Deja la hoja en una forma que `st.markdown` no rompa.

    Streamlit pasa lo que le des por un parser de Markdown **antes** de
    insertarlo en el DOM. Dentro de un `<style>`, una línea en blanco es un fin
    de párrafo: cierra la etiqueta ahí y todo el CSS que sigue se imprime como
    texto en la pantalla. Una línea con cuatro espacios al inicio es un bloque
    de código y hace lo mismo.

    Así que se quitan las líneas vacías y la sangría. El CSS no las necesita y
    el archivo importado sí las tiene, porque está escrito para leerse.
    """
    return "\n".join(l.strip() for l in hoja.splitlines() if l.strip())


def css():
    """El CSS del sistema, más el puente hacia los widgets de Streamlit."""
    with open(CSS, encoding="utf-8") as fh:
        base = fh.read()
    puente = _PUENTE_STREAMLIT % {
        "acento": ACENTO, "hover": ACENTO_HOVER,
        "suave": ACENTO_SUAVE, "tinta": ACENTO_TINTA}
    return compactar(base + puente)


# Las fuentes de la marca son Space Grotesk y Roboto; las dos están en Google
# Fonts, así que se cargan de ahí en vez de servir los .ttf. Si no hay red, el
# fallback a system-ui deja la app perfectamente usable: el sistema de diseño
# no depende de la tipografía para funcionar.
FUENTES = ("https://fonts.googleapis.com/css2?"
           "family=Roboto:wght@300;400;500;700&"
           "family=Space+Grotesk:wght@400;500;600;700&display=swap")

# El puente: Streamlit dibuja sus propios widgets y aquí solo se les cambia el
# color al del sistema. Se toca lo mínimo —fondo, tipografía, pestañas, tablas,
# barra lateral— y nunca la estructura, porque los selectores internos de
# Streamlit cambian entre versiones y una regla de más se rompe sola.
_PUENTE_STREAMLIT = """
/* ── puente Streamlit ─────────────────────────────────────────────────── */
:root{--app-accent:%(acento)s;--app-accent-hover:%(hover)s;
      --app-accent-soft:%(suave)s;--app-accent-ink:%(tinta)s;}
/* Sin `[class*="st-"]`: ese selector agarra TODAS las clases de Streamlit,
   incluidas las de los iconos. Los iconos son una fuente de ligaduras —el
   elemento contiene literalmente el texto "keyboard_double_arrow_right" y la
   fuente lo dibuja como flecha—, asi que al cambiarles la tipografia el nombre
   se imprime encima del boton. Se pone la fuente en el contenedor y se hereda. */
html, body, .stApp{font-family:var(--app-font-body)}
/* Y se le devuelve la suya a los iconos, por si algo mas los alcanza. */
[data-testid="stIconMaterial"], .material-icons, .material-icons-outlined,
.material-symbols-rounded, span[class*="material-symbols"]{
font-family:"Material Symbols Rounded","Material Icons"!important}
.stApp{background:var(--app-bg)}
.block-container{padding-top:2.2rem;max-width:1320px}
/* Con `h2` a secas no alcanza: los encabezados que dibuja Streamlit vienen con
   su propia clase y ganan por especificidad. Se califica con .stApp. */
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,
[data-testid="stMarkdownContainer"] h1,[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,[data-testid="stMarkdownContainer"] h4{
font-family:var(--app-font-display);color:var(--app-ink);letter-spacing:-.01em}
section[data-testid="stSidebar"]{background:var(--app-surface);
               border-right:1px solid var(--app-line)}
section[data-testid="stSidebar"] .stRadio label{font-size:13.5px}

/* pestañas */
.stTabs [data-baseweb="tab-list"]{gap:2px;border-bottom:1px solid var(--app-line)}
.stTabs [data-baseweb="tab"]{height:auto;padding:9px 14px;font-size:13.5px;
    color:var(--app-ink-3);border-radius:var(--app-radius-sm) var(--app-radius-sm) 0 0}
.stTabs [data-baseweb="tab"]:hover{color:var(--app-ink);background:var(--app-surface-2)}
.stTabs [aria-selected="true"]{color:var(--app-ink);background:var(--app-surface);
    font-weight:500;box-shadow:inset 0 2px 0 var(--app-accent)}
.stTabs [data-baseweb="tab-highlight"]{display:none}

/* tablas y gráficas */
[data-testid="stDataFrame"]{border:1px solid var(--app-line);
    border-radius:var(--app-radius);overflow:hidden}
[data-testid="stExpander"]{border:1px solid var(--app-line);
    border-radius:var(--app-radius);background:var(--app-surface)}
[data-testid="stExpander"] summary{font-size:13.5px;color:var(--app-ink)}

/* los avisos de Streamlit, con la paleta del sistema */
[data-testid="stAlert"]{border-radius:var(--app-radius);font-size:13.5px}

/* botones: nunca en el acento, para que ninguno parezca una acción de
   autorizar. Esta app no autoriza y su botonería no debe insinuar que sí. */
.stButton>button{border-radius:var(--app-radius-pill);border:1px solid var(--app-line-strong);
    background:var(--app-surface);color:var(--app-ink-2);font-size:13px;font-weight:500}
.stButton>button:hover{border-color:var(--app-ink-3);color:var(--app-ink);
    background:var(--app-surface-2)}

/* el bloque de código que muestra el resumen ejecutivo */
.stCode, pre{border-radius:var(--app-radius)!important}
"""


def aplicar(st):
    """Inyecta el tema. Se llama una vez, al principio de la app."""
    st.markdown(
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="%s">'
        '<style>%s</style>' % (FUENTES, css()), unsafe_allow_html=True)


def html(st, marcado):
    """Escribe un componente. Envuelto en `.neaop` para heredar el tema.

    Se compacta por lo mismo que la hoja de estilo: un salto de línea suelto en
    el marcado lo parte el parser de Markdown. Los saltos de los datos ya los
    convirtió `esc()` en `<br>`, así que aquí no se pierde nada.
    """
    st.markdown('<div class="neaop">%s</div>' % compactar(marcado),
                unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Componentes
# ─────────────────────────────────────────────────────────────────────────────
def badge_veredicto(veredicto):
    """El veredicto del modelo. Cuatro valores y el 'sin evaluar'.

    `Sin datos suficientes` y `sin evaluar` tienen clase propia a propósito: si
    cayeran en la de rechazado, la pantalla diría que al cliente le fue mal
    cuando lo único que pasa es que todavía no sabemos.
    """
    clase = CLASE_VEREDICTO.get(veredicto, "sinevaluar")
    glifo = GLIFO_VEREDICTO.get(veredicto, "○")
    texto = veredicto or "sin evaluar"
    return ('<span class="neaop-badge neaop-badge--%s">'
            '<span class="neaop-badge__glyph">%s</span> %s</span>'
            % (clase, glifo, esc(texto)))


def badge_severidad(sev):
    s = (sev or "baja").lower()
    clase = s if s in ("alta", "intermedia", "baja") else "baja"
    return ('<span class="neaop-sev neaop-sev--%s">%s %s</span>'
            % (clase, GLIFO_SEVERIDAD.get(clase, "●"), esc(s)))


def badge_estado(estado):
    e = (estado or "abierta").lower()
    clase = e if e in ("abierta", "aceptada", "resuelta") else "abierta"
    return ('<span class="neaop-estado neaop-estado--%s">%s %s</span>'
            % (clase, GLIFO_ESTADO.get(clase, "○"), esc(e)))


def chip_etapa(etapa, atorado=False):
    """La etapa, con su lugar en el flujo. '3/6' contesta '¿voy a la mitad?'."""
    e = (etapa or "").lower()
    try:
        orden = "%d/%d" % (ETAPAS.index(e) + 1, len(ETAPAS))
    except ValueError:
        orden = "—"
    return ('<span class="neaop-etapa%s"><span class="neaop-etapa__ord">%s</span> %s</span>'
            % (" neaop-etapa--atorado" if atorado else "", orden,
               esc(ETAPA_NOMBRE.get(e, e or "—"))))


def flujo_etapas(etapa_actual):
    """Las seis etapas con la actual marcada. Sustituye a la pestaña Historial."""
    e = (etapa_actual or "").lower()
    i_actual = ETAPAS.index(e) if e in ETAPAS else -1
    pasos = []
    for i, nombre in enumerate(ETAPAS):
        if i < i_actual:
            mod = " neaop-flow__step--done"
        elif i == i_actual:
            mod = " neaop-flow__step--current"
        else:
            mod = ""
        pasos.append('<span class="neaop-flow__step%s">%s</span>'
                     % (mod, esc(ETAPA_NOMBRE[nombre])))
    return ('<div class="neaop-flow">%s</div>'
            % '<span class="neaop-flow__sep">›</span>'.join(pasos))


def dias(n, atorado=False):
    return ('<span class="neaop-dias%s">%d d</span>'
            % (" neaop-dias--atorado" if atorado else "", int(n or 0)))


def metrica(etiqueta, valor, pie=None, alerta=False, ausente=False):
    """Una métrica. `ausente` la dibuja en gris chico, nunca como un cero."""
    clase_valor = ("neaop-metric__value neaop-metric__value--missing" if ausente
                   else "neaop-metric__value")
    pie_html = ('<span class="neaop-metric__foot">%s</span>' % esc(pie)) if pie else ""
    return ('<div class="neaop-metric%s"><span class="neaop-metric__label">%s</span>'
            '<span class="%s">%s</span>%s</div>'
            % (" neaop-metric--alert" if alerta else "", esc(etiqueta),
               clase_valor, esc(valor), pie_html))


def metricas(items):
    return '<div class="neaop-metrics">%s</div>' % "".join(items)


def score_titular(score, veredicto, linea_propuesta):
    """El score, su veredicto y la línea que propone el modelo.

    Una línea propuesta de 0 se escribe "no propone". El modelo guarda 0 cuando
    no aprueba, y "$0.00" junto a una línea autorizada de $50,000 se lee como si
    hubiera propuesto cero pesos. No propuso cero: no propuso nada.
    """
    valor = "—" if score is None else "%.4f" % float(score)
    try:
        prop = float(linea_propuesta or 0)
    except (TypeError, ValueError):
        prop = 0
    if prop > 0:
        linea = ('<span class="neaop-num">%s</span>' % pesos(prop))
        pie = "línea que propone el modelo"
    else:
        linea = ('<span style="font-style:italic;color:var(--missing-ink)">'
                 'no propone</span>')
        pie = "el modelo no propone línea; la decide el comité"
    return ('<div class="neaop-stack">'
            '<div class="neaop-score"><span class="neaop-score__value">%s</span>'
            '<span class="neaop-score__scale">/ 1.0000</span>%s</div>'
            '<div class="neaop-row">%s<span class="neaop-note">%s</span></div>'
            '</div>'
            % (valor, badge_veredicto(veredicto), linea, esc(pie)))


def salvedad(modulos_sin_datos, total=4):
    """La advertencia de que el score se calculó incompleto.

    No va en un tooltip. Un score de 0.5163 calculado sobre 3 de 4 módulos no
    es el mismo número que uno completo, y quien lo lea tiene que saberlo sin
    tener que pasar el mouse por encima.
    """
    sin = list(modulos_sin_datos or [])
    if not sin:
        return ""
    nombres = ", ".join(s.replace("modulo_", "").replace("_", " ") for s in sin)
    return ('<div class="neaop-caveat"><span class="neaop-caveat__glyph">◑</span>'
            '<div>Calculado sobre <strong>%d de los %d módulos</strong>. Los pesos '
            'de los que faltan se repartieron entre los demás, así que '
            '<strong>no es comparable</strong> contra un score completo. '
            'Falta: %s.</div></div>'
            % (total - len(sin), total, esc(nombres)))


def modulo(nombre, peso, puntaje):
    """Un módulo del score con su barra.

    Sin datos **no** dibuja una barra en cero: dibuja una barra rayada y dice
    que salió del promedio. Cero es una calificación mala; ausente no lo es, y
    en una barra los dos se ven igual si uno no lo impide.
    """
    if puntaje is None:
        return ('<div class="neaop-modulo neaop-modulo--sindatos">'
                '<div><span class="neaop-modulo__name">%s</span> '
                '<span class="neaop-modulo__peso">peso %.1f%%</span></div>'
                '<span class="neaop-modulo__score">⌀ sin datos</span>'
                '<div class="neaop-modulo__track"></div>'
                '<span class="neaop-modulo__redistrib">Sale del promedio. Su %.1f%% '
                'se repartió entre los demás — no cuenta como cero.</span></div>'
                % (esc(nombre), peso * 100, peso * 100))
    v = max(0.0, min(1.0, float(puntaje)))
    return ('<div class="neaop-modulo">'
            '<div><span class="neaop-modulo__name">%s</span> '
            '<span class="neaop-modulo__peso">peso %.1f%%</span></div>'
            '<span class="neaop-modulo__score">%.4f</span>'
            '<div class="neaop-modulo__track">'
            '<div class="neaop-modulo__fill" style="width:%.1f%%"></div></div></div>'
            % (esc(nombre), peso * 100, v, v * 100))


def observacion(o):
    """Una observación, con su justificación firmada completa.

    La justificación no se trunca ni se resume: es el documento que sostiene por
    qué se asumió un riesgo, y va firmada. Un "ver más" aquí es esconder la
    parte que importa.
    """
    sev = (o.get("severidad") or "baja").lower()
    if sev not in ("alta", "intermedia", "baja"):
        sev = "baja"
    desc = o.get("descripcion") or ""
    titulo = desc.split(" — ")[0]
    cuerpo = desc[len(titulo) + 3:] if " — " in desc else ""

    partes = ['<div class="neaop-obs neaop-obs--%s"><div class="neaop-obs__bar"></div>'
              '<div class="neaop-obs__head">%s%s'
              '<span class="neaop-obs__title">%s</span></div>'
              % (sev, badge_severidad(sev), badge_estado(o.get("estado")),
                 esc(titulo))]
    if cuerpo:
        partes.append('<div class="neaop-obs__body"><p>%s</p></div>' % esc(cuerpo))
    if o.get("pedir"):
        partes.append('<div class="neaop-obs__body"><p><b>Se le pide al cliente:</b> '
                      '%s</p></div>' % esc(o["pedir"]))
    if o.get("justificacion"):
        firma = ['<b>%s</b>' % esc(o.get("aceptada_por") or "sin nombre")]
        if o.get("aceptada_el"):
            firma.append(esc(o["aceptada_el"]))
        partes.append('<div class="neaop-obs__just">'
                      '<div class="neaop-obs__just-label">Justificación de la '
                      'aceptación — el riesgo sigue asumido</div>'
                      '<div class="neaop-obs__just-text">%s</div>'
                      '<div class="neaop-obs__sign">%s</div></div>'
                      % (esc(o["justificacion"]), "".join(
                          "<span>%s</span>" % f for f in firma)))
    meta = []
    if o.get("fecha"):
        meta.append("Detectada el %s" % esc(o["fecha"]))
    if o.get("clase"):
        meta.append("Clase: %s" % esc(o["clase"]))
    if o.get("resuelta_por"):
        meta.append("Resuelta por %s" % esc(o["resuelta_por"]))
    if meta:
        partes.append('<div class="neaop-obs__meta">%s</div>'
                      % "".join("<span>%s</span>" % m for m in meta))
    partes.append("</div>")
    return "".join(partes)


def campo(c):
    """Un campo del alta, en uno de sus tres estados.

    Con valor, `FALTA` (hay que conseguirlo) y `— vacío a propósito —` (una
    decisión, con su motivo). Los tres se ven distinto porque significan cosas
    distintas y en un formulario los tres se ven igual: vacíos.
    """
    valor, tipo = c.get("valor"), c.get("tipo")
    nota = c.get("nota")
    mod, texto = "", ""

    if tipo == "checkbox":
        texto = "☑ marcar" if valor else "☐ dejar sin marcar"
    elif tipo == "casillas":
        # Se dibujan todas las opciones, marcadas y sin marcar. El formulario del
        # Django las muestra completas y lo que hay que ver es cuáles NO van: una
        # lista de solo las marcadas obliga a comparar contra la pantalla.
        marcadas = valor or []
        texto = "   ".join("%s %s" % ("☑" if o in marcadas else "☐", o)
                           for o in (c.get("opciones") or marcadas))
    elif tipo == "sistema":
        mod, texto = " neaop-field--vacio", str(valor or "")
    elif valor in (None, "", []):
        if c.get("opcional"):
            mod, texto = " neaop-field--vacio", "— vacío a propósito —"
        else:
            mod, texto = " neaop-field--falta", "FALTA"
    else:
        texto = str(valor)

    nota_html = ('<span class="neaop-field__note">%s</span>' % _con_enlaces(nota)) if nota else ""
    return ('<div class="neaop-field%s"><span class="neaop-field__label">%s</span>'
            '<span class="neaop-field__value">'
            '<span class="neaop-field__box">%s</span></span>%s</div>'
            % (mod, esc(c.get("etiqueta")), esc(texto), nota_html))


def bloque_detiene(texto):
    return ('<div class="neaop-block"><div>'
            '<div class="neaop-block__label">Qué lo detiene</div>'
            '<div class="neaop-block__text">%s</div></div></div>' % esc(texto))


def fila_expediente(f, bloqueo, atorado):
    """Un renglón de la tabla del tablero."""
    score = f.get("score")
    if score is None:
        celda_score = '<span class="neaop-note">—</span>'
    else:
        celda_score = '<span class="neaop-num">%.4f</span>' % float(score)
    return ('<tr><td class="neaop-folio">%s</td><td class="neaop-razon">%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
            '<td class="neaop-detiene%s">%s</td></tr>'
            % (esc(f.get("folio")), esc((f.get("razon_social") or "")[:46]),
               chip_etapa(f.get("etapa"), atorado),
               dias(f.get("dias_en_etapa"), atorado), celda_score,
               badge_veredicto(f.get("veredicto")),
               "" if bloqueo else " neaop-detiene--none", esc(bloqueo or "—")))


def tabla_expedientes(filas_html):
    return ('<table class="neaop-table"><thead><tr>'
            '<th>Folio</th><th>Razón social</th><th>Etapa</th><th>Días</th>'
            '<th>Score</th><th>Veredicto</th><th>Qué lo detiene</th>'
            '</tr></thead><tbody>%s</tbody></table>' % "".join(filas_html))


def documento(texto):
    """El resumen ejecutivo como documento, no como bloque de código."""
    return '<div class="neaop-doc">%s</div>' % esc(texto)
