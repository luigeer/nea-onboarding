# -*- coding: utf-8 -*-
"""
generar_anexo_razonado.py — Anexo de Análisis Razonado del Beneficiario Controlador
==================================================================================
Documento interno de Grit que sustenta la determinación del beneficiario controlador
cuando ésta no se resuelve por participación directa. Lo firma únicamente el
responsable de cumplimiento; el cliente no lo suscribe.

Se genera en tres supuestos:
  1. El criterio aplicado fue control efectivo y no participación
  2. No fue posible identificar a una persona física
  3. La estructura accionaria documentada deja una brecha de 25% o más

Fundamento: Manual de Prevención de Lavado de Dinero de Grit, apartado 8.4.11;
art. 3 fracción III LFPIORPI; art. 12 fracción VII de las Reglas de Carácter General;
arts. 32-B Ter y 32-B Quáter CFF.

Uso:
    python generar_anexo_razonado.py <datos.json> <salida.pdf>
"""

import json
import os
import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, KeepTogether)

# ─────────────────────────────────────────────────────────────────────────────
NEA_CORAL = colors.HexColor("#F1654B")
GRIS_BARRA = colors.HexColor("#EFEFEF")
GRIS_LINEA = colors.HexColor("#BFBFBF")
TEXTO = colors.HexColor("#1A1A1A")

SUJETO_OBLIGADO = "Grit Payment Solutions, S.A.P.I. de C.V. / NEA Card"
MARGEN = 15 * mm
ANCHO_UTIL = letter[0] - 2 * MARGEN

UMBRAL = 25.0

# Los tres supuestos de control efectivo del Manual, apartado 8.4.11
SUPUESTOS_CONTROL = [
    ("imponer_decisiones",
     "Imponer, directa o indirectamente, decisiones en las asambleas generales de accionistas "
     "o nombrar o destituir a la mayoría de los consejeros, administradores o sus equivalentes"),
    ("derechos_voto",
     "Mantener la titularidad de los derechos que permitan ejercer el voto respecto de más del "
     "25% del capital social"),
    ("dirigir_administracion",
     "Dirigir, directa o indirectamente, la administración, la estrategia o las principales "
     "políticas de la persona moral"),
]

# Exclusiones expresas y funcionales que se aplican en toda determinación
EXCLUSIONES = [
    "El cliente mismo, por no poder ser beneficiario controlador de sí mismo",
    "Los poderdantes o mandantes cuyos apoderados celebren el acto u operación, conforme al "
    "Manual",
    "El comisario, cuya función es de vigilancia y no de control",
    "El apoderado que únicamente ejecuta actos sin facultades de decisión sobre la "
    "administración o la estrategia",
]

CONCLUSIONES = {
    "control_efectivo": "Se identificó beneficiario controlador por control efectivo",
    "no_identificado": "No fue posible identificar a una persona física o grupo determinado",
    "parcial": "Identificación parcial",
}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ─────────────────────────────────────────────────────────────────────────────
def _estilos():
    base = dict(fontName="Helvetica", fontSize=8, leading=10.5, textColor=TEXTO)
    return {
        "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
                                 alignment=TA_CENTER, textColor=TEXTO),
        "subtitulo": ParagraphStyle("st", fontName="Helvetica", fontSize=6.8, leading=8.5,
                                    alignment=TA_CENTER, textColor=colors.HexColor("#555555")),
        "seccion": ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=8.2, leading=10,
                                  textColor=TEXTO),
        "cuerpo": ParagraphStyle("c", **base),
        "justo": ParagraphStyle("j", alignment=TA_JUSTIFY, **base),
        "cita": ParagraphStyle("q", fontName="Helvetica-Oblique", fontSize=8, leading=10.5,
                               leftIndent=14, rightIndent=14, textColor=TEXTO),
        "pie": ParagraphStyle("p", fontName="Helvetica-Oblique", fontSize=6.5, leading=8,
                              textColor=colors.HexColor("#555555")),
        "firma": ParagraphStyle("f", fontName="Helvetica-Bold", fontSize=8, leading=10,
                                alignment=TA_CENTER, textColor=TEXTO),
        "firma_sub": ParagraphStyle("fs", fontName="Helvetica", fontSize=7, leading=9,
                                    alignment=TA_CENTER, textColor=colors.HexColor("#555555")),
    }


def _barra(texto, S):
    t = Table([[Paragraph(texto, S["seccion"])]], colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_BARRA),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, NEA_CORAL),
    ]))
    return t


def _campos(pares, S, cols=2):
    filas, buf = [], []
    for et, val in pares:
        if val in (None, ""):
            continue
        full = et.startswith("*")
        celda = Paragraph("<b>%s:</b> %s" % (et.lstrip("*"), val), S["cuerpo"])
        if full:
            if buf:
                filas.append(buf + [""] * (cols - len(buf)))
                buf = []
            filas.append([celda] + [""] * (cols - 1))
        else:
            buf.append(celda)
            if len(buf) == cols:
                filas.append(buf)
                buf = []
    if buf:
        filas.append(buf + [""] * (cols - len(buf)))
    t = Table(filas, colWidths=[ANCHO_UTIL / cols] * cols)
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
           ("LINEBELOW", (0, 0), (-1, -2), 0.25, GRIS_LINEA)]
    for i, f in enumerate(filas):
        if f[1:] == [""] * (cols - 1) and f[0] != "":
            est.append(("SPAN", (0, i), (-1, i)))
    t.setStyle(TableStyle(est))
    return t


def _lista(items, S, numerada=False):
    out = []
    for i, it in enumerate(items, start=1):
        marca = "%d." % i if numerada else "&bull;"
        out.append(Paragraph("%s&nbsp;&nbsp;%s" % (marca, it), S["justo"]))
        out.append(Spacer(1, 2))
    return out


def _casilla(v):
    return "[X]" if v else "[  ]"


def _pct(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return "%s%%" % format(float(v), ".2f").rstrip("0").rstrip(".")


# ─────────────────────────────────────────────────────────────────────────────
def _encabezado(D, S):
    return [
        Paragraph("ANEXO DE ANÁLISIS RAZONADO DEL BENEFICIARIO CONTROLADOR", S["titulo"]),
        Spacer(1, 2),
        Paragraph("Manual de Prevención de Lavado de Dinero, apartado 8.4.11 &mdash; art. 3 "
                  "fracción III LFPIORPI &mdash; art. 12 fracción VII de las Reglas de Carácter "
                  "General &mdash; arts. 32-B Ter y 32-B Quáter CFF", S["subtitulo"]),
        Spacer(1, 8),
    ]


def _s1(D, S):
    cl = D["cliente"]
    pares = [("*Denominación o razón social", cl.get("razon_social")),
             ("RFC", cl.get("rfc")),
             ("Folio del expediente", D.get("folio")),
             ("*Actividad vulnerable", cl.get("actividad_vulnerable",
                                              "Emisión y comercialización de tarjetas de servicio")),
             ("Fecha del acto u operación", cl.get("fecha_operacion")),
             ("Fecha del presente análisis", D["fecha"])]
    return [_barra("I. IDENTIFICACIÓN DEL CLIENTE Y DE LA OPERACIÓN", S), Spacer(1, 4),
            _campos(pares, S), Spacer(1, 8)]


def _s2(D, S):
    so = D.get("solicitud", {})
    pares = [("Fecha de la solicitud", so.get("fecha")),
             ("Medio", so.get("medio")),
             ("*Dirigida a", so.get("dirigida_a")),
             ("*Constancia", so.get("referencia",
                                    "Formato de Identificación PLD del expediente, apartado "
                                    "«Constancia de la existencia de algún beneficiario "
                                    "controlador»"))]
    return [_barra("II. SOLICITUD FORMULADA AL CLIENTE", S), Spacer(1, 4),
            _campos(pares, S), Spacer(1, 8)]


def _s3(D, S):
    re_ = D.get("respuesta", {})
    out = [_barra("III. RESPUESTA DEL CLIENTE", S), Spacer(1, 4)]
    if re_.get("leyenda"):
        out += [Paragraph("El cliente asentó y firmó la siguiente declaración:", S["cuerpo"]),
                Spacer(1, 3),
                Paragraph("&laquo;%s&raquo;" % re_["leyenda"], S["cita"]),
                Spacer(1, 5)]
    pares = [("Fecha", re_.get("fecha")),
             ("Firmante", re_.get("firmante")),
             ("*Cargo", re_.get("cargo"))]
    out += [_campos(pares, S)]
    if re_.get("observacion"):
        out += [Spacer(1, 4), Paragraph(re_["observacion"], S["justo"])]
    out.append(Spacer(1, 8))
    return out


def _s4(D, S):
    docs = D.get("documentacion_revisada") or []
    out = [_barra("IV. DOCUMENTACIÓN REVISADA", S), Spacer(1, 4)]
    if docs:
        out += _lista(docs, S)
    else:
        out.append(Paragraph("No se asentó documentación revisada.", S["cuerpo"]))
    out.append(Spacer(1, 6))
    return out


def _s5(D, S):
    an = D.get("analisis_participacion", {})
    out = [_barra("V. ANÁLISIS POR PARTICIPACIÓN — PRIMER CRITERIO", S), Spacer(1, 4)]
    out.append(Paragraph("Se verificó si alguna persona física mantiene, de manera directa o "
                         "indirecta, una participación de %s o más del capital social, de los "
                         "derechos de voto o del derecho a recibir beneficios económicos."
                         % _pct(UMBRAL), S["justo"]))
    out.append(Spacer(1, 5))

    tabla = an.get("tabla") or []
    if tabla:
        filas = [[Paragraph("<b>Accionista</b>", S["cuerpo"]),
                  Paragraph("<b>Naturaleza</b>", S["cuerpo"]),
                  Paragraph("<b>%</b>", S["cuerpo"])]]
        total = 0.0
        for a in tabla:
            filas.append([Paragraph((a.get("accionista") or "").upper(), S["cuerpo"]),
                          Paragraph(a.get("naturaleza", ""), S["cuerpo"]),
                          Paragraph(_pct(a.get("porcentaje")) or "", S["cuerpo"])])
            try:
                total += float(a.get("porcentaje") or 0)
            except (TypeError, ValueError):
                pass
        filas.append([Paragraph("<b>TOTAL DOCUMENTADO</b>", S["cuerpo"]), Paragraph("", S["cuerpo"]),
                      Paragraph("<b>%s</b>" % _pct(total), S["cuerpo"])])
        t = Table(filas, colWidths=[ANCHO_UTIL * 0.52, ANCHO_UTIL * 0.30, ANCHO_UTIL * 0.18])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GRIS_BARRA),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.25, GRIS_LINEA),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, TEXTO),
        ]))
        out += [t, Spacer(1, 5)]
        brecha = round(100.0 - total, 2)
        if abs(brecha) > 0.01:
            aviso = "La estructura documentada deja una diferencia de %s sin identificar." % _pct(brecha)
            if brecha >= UMBRAL:
                aviso += (" Por ser igual o mayor al umbral, dicha diferencia podría albergar a una "
                          "persona física con la calidad de beneficiario controlador, lo que impide "
                          "afirmar que la identificación sea completa.")
            out += [Paragraph(aviso, S["justo"]), Spacer(1, 5)]

    for r in an.get("rastreo") or []:
        out += [Paragraph(r, S["justo"]), Spacer(1, 3)]

    if an.get("conclusion"):
        out += [Spacer(1, 2),
                Paragraph("<b>Conclusión del primer criterio.</b> %s" % an["conclusion"], S["justo"])]
    out.append(Spacer(1, 8))
    return out


def _s6(D, S):
    an = D.get("analisis_control_efectivo", {})
    ev = an.get("supuestos", {})
    out = [_barra("VI. ANÁLISIS DE CONTROL EFECTIVO — SEGUNDO CRITERIO", S), Spacer(1, 4)]
    out.append(Paragraph("Al no resolverse la determinación por participación, se evaluaron los "
                         "tres supuestos de control efectivo:", S["justo"]))
    out.append(Spacer(1, 4))
    for clave, texto in SUPUESTOS_CONTROL:
        val = ev.get(clave)
        marcado = bool(val) if not isinstance(val, str) else True
        out.append(Paragraph("%s&nbsp;&nbsp;%s" % (_casilla(marcado), texto), S["justo"]))
        if isinstance(val, str) and val.strip():
            out.append(Spacer(1, 1))
            out.append(Paragraph(val, S["cita"]))
        out.append(Spacer(1, 3))

    out += [Spacer(1, 3), Paragraph("<b>Exclusiones aplicadas.</b>", S["cuerpo"]), Spacer(1, 3)]
    out += _lista(an.get("exclusiones") or EXCLUSIONES, S)

    if an.get("conclusion"):
        out += [Spacer(1, 3),
                Paragraph("<b>Conclusión del segundo criterio.</b> %s" % an["conclusion"], S["justo"])]
    out.append(Spacer(1, 8))
    return out


def _s7(D, S):
    co = D.get("conclusion", {})
    tipo = co.get("tipo", "no_identificado")
    out = [_barra("VII. CONCLUSIÓN", S), Spacer(1, 4)]
    for clave, etiqueta in CONCLUSIONES.items():
        out.append(Paragraph("%s&nbsp;&nbsp;%s" % (_casilla(clave == tipo), etiqueta), S["cuerpo"]))
        out.append(Spacer(1, 2))
    out.append(Spacer(1, 4))

    benes = co.get("beneficiarios") or []
    if benes:
        out.append(Paragraph("<b>Personas determinadas como beneficiario controlador:</b>", S["cuerpo"]))
        out.append(Spacer(1, 3))
        out += _lista(["<b>%s</b> &mdash; %s" % (b.get("nombre", ""), b.get("fundamento", ""))
                       for b in benes], S, numerada=True)
        out.append(Spacer(1, 3))

    if co.get("razonamiento"):
        out += [Paragraph("<b>Razonamiento.</b> %s" % co["razonamiento"], S["justo"]), Spacer(1, 4)]
    out.append(Spacer(1, 4))
    return out


def _s8(D, S):
    """Medidas adoptadas. Solo aplica si la conclusión no cerró la identificación."""
    tipo = D.get("conclusion", {}).get("tipo", "no_identificado")
    if tipo == "control_efectivo":
        return []
    me = D.get("medidas", {})
    pares = [("Grado de riesgo asignado", me.get("grado_riesgo")),
             ("Reclasificación", me.get("reclasificacion")),
             ("*Monitoreo", me.get("monitoreo")),
             ("*Escalamiento", me.get("escalamiento"))]
    out = [_barra("VIII. MEDIDAS ADOPTADAS", S), Spacer(1, 4), _campos(pares, S), Spacer(1, 4)]
    out.append(Paragraph("Se hace constar que el expediente de identificación no se tuvo por "
                         "integrado de forma automática por virtud de la declaración del cliente, "
                         "y que las medidas anteriores se adoptaron con motivo del resultado de "
                         "este análisis.", S["justo"]))
    if me.get("notas"):
        out += [Spacer(1, 3), Paragraph(me["notas"], S["justo"])]
    out.append(Spacer(1, 8))
    return out


def _s9(D, S):
    rc = D.get("responsable", {})
    nombre = (rc.get("nombre") or "").upper()
    cargo = rc.get("cargo", "Responsable de Cumplimiento / Oficial de Cumplimiento PLD")
    texto = ("El suscrito hace constar que el presente análisis se realizó con la documentación "
             "que obra en el expediente de identificación del cliente y que refleja el "
             "razonamiento seguido para la determinación del beneficiario controlador, en "
             "cumplimiento del Manual de Prevención de Lavado de Dinero, de la LFPIORPI, su "
             "Reglamento y las Reglas de Carácter General.")
    bloque = Table([[""]], colWidths=[ANCHO_UTIL * 0.45],
                   style=TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.6, TEXTO)]))
    firma = Table([[[bloque, Spacer(1, 3),
                     Paragraph(nombre, S["firma"]), Paragraph(cargo, S["firma_sub"]),
                     Paragraph(SUJETO_OBLIGADO, S["firma_sub"])]]],
                  colWidths=[ANCHO_UTIL])
    firma.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                               ("LEFTPADDING", (0, 0), (-1, -1), ANCHO_UTIL * 0.27)]))
    pares = [("Lugar", D.get("lugar", "Ciudad de México")), ("Fecha", D["fecha"])]
    return [KeepTogether([_barra("IX. CONSTANCIA Y FIRMA", S), Spacer(1, 4),
                          Paragraph(texto, S["justo"]), Spacer(1, 4),
                          _campos(pares, S), Spacer(1, 22),
                          firma, Spacer(1, 6),
                          Paragraph("Este anexo es un documento interno del sujeto obligado. El "
                                    "cliente no lo suscribe.", S["pie"])])]


# ─────────────────────────────────────────────────────────────────────────────
def _pie(canv, doc):
    canv.saveState()
    canv.setStrokeColor(NEA_CORAL)
    canv.setLineWidth(1.2)
    canv.line(MARGEN, 12 * mm, letter[0] - MARGEN, 12 * mm)
    canv.setFont("Helvetica", 6.5)
    canv.setFillColor(colors.HexColor("#555555"))
    canv.drawString(MARGEN, 8.5 * mm, "%s — Anexo de Análisis Razonado" % SUJETO_OBLIGADO)
    canv.drawRightString(letter[0] - MARGEN, 8.5 * mm, "Página %d" % canv.getPageNumber())
    canv.restoreState()


def _validar(D):
    if not D.get("cliente", {}).get("razon_social"):
        raise ValueError("Falta cliente.razon_social")
    tipo = D.get("conclusion", {}).get("tipo")
    if tipo not in CONCLUSIONES:
        raise ValueError("conclusion.tipo inválido: %r. Válidos: %s" % (tipo, sorted(CONCLUSIONES)))
    if tipo == "control_efectivo" and not D.get("conclusion", {}).get("beneficiarios"):
        raise ValueError("Con conclusión de control efectivo debe listarse al menos un "
                         "beneficiario con su fundamento.")
    if tipo != "control_efectivo" and not D.get("conclusion", {}).get("razonamiento"):
        raise ValueError("Sin identificación completa, el Manual exige asentar el razonamiento.")
    if not D.get("responsable", {}).get("nombre"):
        raise ValueError("Falta responsable.nombre: el anexo lo firma cumplimiento.")
    if not D.get("fecha"):
        hoy = date.today()
        D["fecha"] = "%d de %s de %d" % (hoy.day, MESES[hoy.month - 1], hoy.year)
    return D


def generar_anexo_razonado(datos: dict, output_path: str):
    """Genera el Anexo de Análisis Razonado del Beneficiario Controlador."""
    D = _validar(dict(datos))
    S = _estilos()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = BaseDocTemplate(output_path, pagesize=letter,
                          leftMargin=MARGEN, rightMargin=MARGEN,
                          topMargin=MARGEN, bottomMargin=18 * mm,
                          title="Anexo de Análisis Razonado del Beneficiario Controlador",
                          author=SUJETO_OBLIGADO)
    doc.addPageTemplates([PageTemplate(id="std", onPage=_pie, frames=[
        Frame(MARGEN, 18 * mm, ANCHO_UTIL, letter[1] - MARGEN - 18 * mm, id="cuerpo",
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])])

    story = []
    for fn in (_encabezado, _s1, _s2, _s3, _s4, _s5, _s6, _s7, _s8, _s9):
        story += fn(D, S)
    doc.build(story)
    print("Anexo de análisis razonado generado: %s" % output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        generar_anexo_razonado(json.load(fh), sys.argv[2])
