# -*- coding: utf-8 -*-
"""
generar_beneficiario.py — Formato de Identificación del Beneficiario Controlador
================================================================================
Genera el "Formato A" de Nea: identificación del beneficiario controlador de una
persona moral, conforme a los artículos 32-B Ter, 32-B Quáter y 32-B Quinquies del
CFF, las Reglas 2.8.22 a 2.8.24 de la RMF y la LFPIORPI.

A diferencia del contrato y del formato PLD, este documento NO se sobrepone a un
template: su estructura es variable (número de beneficiarios, largo de la tabla
accionaria), así que se construye con flowables y pagina solo.

Umbral de participación: 25% o más (criterio Nea, jul 2026).

Uso:
    python generar_beneficiario.py <datos.json> <salida.pdf>

Estructura del diccionario de datos: ver DATOS_EJEMPLO al final del módulo.
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
# Constantes de marca y de layout
# ─────────────────────────────────────────────────────────────────────────────
NEA_CORAL = colors.HexColor("#F1654B")
GRIS_BARRA = colors.HexColor("#EFEFEF")
GRIS_LINEA = colors.HexColor("#BFBFBF")
TEXTO = colors.HexColor("#1A1A1A")

SUJETO_OBLIGADO = "Grit Payment Solutions, S.A.P.I. de C.V. / NEA Card"
DOMICILIO_RESPONSABLE = ("Calle 3 Picos 65, Polanco V Sección, Miguel Hidalgo, "
                         "Ciudad de México, C.P. 11560, tel. 5521207273")

MARGEN = 15 * mm
ANCHO_UTIL = letter[0] - 2 * MARGEN

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

CRITERIOS = {
    "participacion": ("Art. 32-B Ter, fracción I CFF — Participación de 25% o más del capital "
                      "social, de los derechos de voto o del derecho a recibir beneficios "
                      "económicos, de manera directa o indirecta"),
    "control_efectivo": ("Art. 32-B Ter, fracción II CFF y art. 3 fracción III LFPIORPI — "
                         "Control efectivo en última instancia, sin alcanzar el umbral de "
                         "participación"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Estilos
# ─────────────────────────────────────────────────────────────────────────────
def _estilos():
    base = dict(fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=TEXTO)
    return {
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=10.5,
                                 leading=13, alignment=TA_CENTER, textColor=TEXTO),
        "subtitulo": ParagraphStyle("subtitulo", fontName="Helvetica", fontSize=6.8,
                                    leading=8.5, alignment=TA_CENTER,
                                    textColor=colors.HexColor("#555555")),
        "seccion": ParagraphStyle("seccion", fontName="Helvetica-Bold", fontSize=8.2,
                                  leading=10, textColor=TEXTO),
        "sub": ParagraphStyle("sub", fontName="Helvetica-Bold", fontSize=7.6,
                              leading=9.5, textColor=NEA_CORAL),
        "cuerpo": ParagraphStyle("cuerpo", **base),
        "justo": ParagraphStyle("justo", alignment=TA_JUSTIFY, **base),
        "pie": ParagraphStyle("pie", fontName="Helvetica-Oblique", fontSize=6.5,
                              leading=8, textColor=colors.HexColor("#555555")),
        "firma": ParagraphStyle("firma", fontName="Helvetica-Bold", fontSize=8,
                                leading=10, alignment=TA_CENTER, textColor=TEXTO),
        "firma_sub": ParagraphStyle("firma_sub", fontName="Helvetica", fontSize=7,
                                    leading=9, alignment=TA_CENTER,
                                    textColor=colors.HexColor("#555555")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de construcción
# ─────────────────────────────────────────────────────────────────────────────
def _barra(texto, S):
    """Encabezado de sección con fondo gris."""
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
    """Rejilla de etiqueta/valor. 'pares' es lista de (etiqueta, valor).

    Un par cuyo valor sea None se omite; una etiqueta que empiece con '*'
    ocupa el ancho completo del renglón.
    """
    filas, buffer = [], []
    anchos_par = ANCHO_UTIL / cols
    for etiqueta, valor in pares:
        if valor in (None, ""):
            continue
        ancho_completo = etiqueta.startswith("*")
        et = etiqueta.lstrip("*")
        celda = Paragraph("<b>%s:</b> %s" % (et, valor), S["cuerpo"])
        if ancho_completo:
            if buffer:
                filas.append(buffer + [""] * (cols - len(buffer)))
                buffer = []
            filas.append([celda] + [""] * (cols - 1))
        else:
            buffer.append(celda)
            if len(buffer) == cols:
                filas.append(buffer)
                buffer = []
    if buffer:
        filas.append(buffer + [""] * (cols - len(buffer)))

    t = Table(filas, colWidths=[anchos_par] * cols)
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, GRIS_LINEA),
    ]
    # celdas de ancho completo: fusionar
    for i, fila in enumerate(filas):
        if fila[1:] == [""] * (cols - 1) and fila[0] != "":
            estilo.append(("SPAN", (0, i), (-1, i)))
    t.setStyle(TableStyle(estilo))
    return t


def _casilla(marcada):
    return "[X]" if marcada else "[  ]"


def _fmt_moneda(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return "$%s M.N." % format(v, ",.2f")


def _fmt_pct(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return "%s%%" % format(v, ".2f").rstrip("0").rstrip(".")


# ─────────────────────────────────────────────────────────────────────────────
# Secciones
# ─────────────────────────────────────────────────────────────────────────────
def _encabezado(D, S):
    out = [
        Paragraph("FORMATO DE IDENTIFICACIÓN DEL BENEFICIARIO CONTROLADOR", S["titulo"]),
        Spacer(1, 2),
        Paragraph("Artículos 32-B Ter, 32-B Quáter y 32-B Quinquies del Código Fiscal de la "
                  "Federación &mdash; Reglas 2.8.22 a 2.8.24 RMF &mdash; LFPIORPI", S["subtitulo"]),
        Spacer(1, 6),
    ]
    meta = Table([[
        Paragraph("<b>Sujeto Obligado:</b> %s" % SUJETO_OBLIGADO, S["cuerpo"]),
        Paragraph("<b>Fecha de llenado:</b> %s" % D["fecha_llenado"], S["cuerpo"]),
        Paragraph("<b>No. de folio:</b> %s" % D.get("folio", ""), S["cuerpo"]),
    ]], colWidths=[ANCHO_UTIL * 0.50, ANCHO_UTIL * 0.25, ANCHO_UTIL * 0.25])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, GRIS_LINEA),
    ]))
    out += [meta, Spacer(1, 8)]
    return out


def _seccion_i(D, S):
    cl = D["cliente"]
    ins = cl.get("instrumento", {})
    fed = cl.get("fedatario", {})
    instrumento = None
    if ins:
        instrumento = "Escritura Pública No. %s%s, de fecha %s" % (
            ins.get("numero", ""),
            (", Libro %s" % ins["libro"]) if ins.get("libro") else "",
            ins.get("fecha", ""))
    fedatario = None
    if fed:
        fedatario = "%s, Notario Público No. %s%s" % (
            fed.get("nombre", ""), fed.get("numero", ""),
            (" de %s" % fed["plaza"]) if fed.get("plaza") else "")

    pares = [
        ("*Denominación o razón social", cl.get("razon_social")),
        ("RFC", cl.get("rfc")),
        ("Fecha de constitución", cl.get("fecha_constitucion")),
        ("*Instrumento público", instrumento),
        ("*Fedatario público", fedatario),
        ("*Autorización de denominación", cl.get("cud_economia")),
        ("*Domicilio fiscal", cl.get("domicilio_fiscal")),
        ("Domicilio social", cl.get("domicilio_social")),
        ("Duración", cl.get("duracion")),
        ("*Actividad económica", cl.get("actividad_economica")),
        ("Régimen fiscal", cl.get("regimen_fiscal")),
        ("Inicio de operaciones", cl.get("inicio_operaciones")),
        ("*Capital social", _fmt_moneda(cl.get("capital_social"))),
        ("*Acciones", cl.get("acciones")),
    ]
    return [_barra("I. DATOS GENERALES DE LA PERSONA MORAL (CLIENTE)", S),
            Spacer(1, 4), _campos(pares, S), Spacer(1, 8)]


def _ficha_beneficiario(b, i, S):
    ident = b.get("identificacion", {})
    id_txt = None
    if ident:
        id_txt = "%s%s%s" % (
            ident.get("tipo", ""),
            (", %s %s" % (ident.get("dato_nombre", "número"), ident["dato"])) if ident.get("dato") else "",
            (" — Vigencia: %s" % ident["vigencia"]) if ident.get("vigencia") else "")

    part = b.get("participacion", {})
    part_txt = None
    if part:
        part_txt = "%s del capital social%s" % (
            _fmt_pct(part.get("porcentaje")),
            (" — %s" % _fmt_moneda(part["monto"])) if part.get("monto") else "")

    interm = b.get("sociedad_intermedia") or {}
    cadena = None
    if interm:
        cadena = ("A través de %s (RFC %s), que participa con %s en el cliente; la persona "
                  "física participa con %s en dicha sociedad" % (
                      interm.get("razon_social", ""), interm.get("rfc", ""),
                      _fmt_pct(interm.get("pct_en_entidad")),
                      _fmt_pct(interm.get("pct_persona_en_intermedia"))))

    pares = [
        ("*Nombre completo", (b.get("nombre") or "").upper()),
        ("Fecha de nacimiento", b.get("fecha_nacimiento")),
        ("Lugar de nacimiento", b.get("lugar_nacimiento")),
        ("Nacionalidad", b.get("nacionalidad")),
        ("País de residencia", b.get("pais_residencia")),
        ("CURP", b.get("curp")),
        ("RFC", b.get("rfc")),
        ("Estado civil", b.get("estado_civil")),
        ("Ocupación", b.get("ocupacion")),
        ("*Domicilio", b.get("domicilio")),
        ("*Identificación oficial", id_txt),
        ("*Participación", part_txt),
        ("*Desglose de acciones", b.get("desglose_acciones")),
        ("*Criterio de determinación", b.get("criterio_determinacion")),
        ("*Cadena de control", cadena),
        ("Forma de participación", b.get("forma_participacion")),
        ("PEP", b.get("pep")),
        ("*Cargo en la sociedad", b.get("cargo")),
        ("*Beneficiario controlador desde", b.get("desde")),
    ]
    return KeepTogether([
        Paragraph("BENEFICIARIO CONTROLADOR %d" % i, S["sub"]),
        Spacer(1, 2),
        _campos(pares, S),
        Spacer(1, 6),
    ])


def _seccion_ii(D, S):
    crit = D.get("criterio_identificacion", "participacion")
    lineas = []
    for clave, texto in CRITERIOS.items():
        lineas.append(Paragraph("%s %s" % (_casilla(clave == crit), texto), S["cuerpo"]))
        lineas.append(Spacer(1, 2))

    out = [_barra("II. IDENTIFICACIÓN DE LOS BENEFICIARIOS CONTROLADORES", S), Spacer(1, 4)]
    out.append(Paragraph("<b>Criterio de identificación aplicado:</b>", S["cuerpo"]))
    out.append(Spacer(1, 2))
    out += lineas
    out.append(Spacer(1, 4))
    for i, b in enumerate(D.get("beneficiarios", []), start=1):
        out.append(_ficha_beneficiario(b, i, S))
    return out


def _seccion_iii(D, S):
    out = [_barra("III. ESTRUCTURA ACCIONARIA Y ÓRGANO DE ADMINISTRACIÓN", S), Spacer(1, 4)]

    filas = [[Paragraph("<b>Accionista</b>", S["cuerpo"]),
              Paragraph("<b>Acciones</b>", S["cuerpo"]),
              Paragraph("<b>Importe</b>", S["cuerpo"]),
              Paragraph("<b>%</b>", S["cuerpo"])]]
    tot_acc = tot_imp = tot_pct = 0.0
    numerico = True
    for a in D.get("estructura_accionaria", []):
        filas.append([Paragraph((a.get("accionista") or "").upper(), S["cuerpo"]),
                      Paragraph(str(a.get("acciones", "")), S["cuerpo"]),
                      Paragraph(_fmt_moneda(a.get("importe")) or "", S["cuerpo"]),
                      Paragraph(_fmt_pct(a.get("porcentaje")) or "", S["cuerpo"])])
        try:
            tot_acc += float(a.get("acciones") or 0)
            tot_imp += float(a.get("importe") or 0)
            tot_pct += float(a.get("porcentaje") or 0)
        except (TypeError, ValueError):
            numerico = False

    if numerico and filas[1:]:
        filas.append([Paragraph("<b>TOTAL</b>", S["cuerpo"]),
                      Paragraph("<b>%s</b>" % format(int(tot_acc), ","), S["cuerpo"]),
                      Paragraph("<b>%s</b>" % _fmt_moneda(tot_imp), S["cuerpo"]),
                      Paragraph("<b>%s</b>" % _fmt_pct(tot_pct), S["cuerpo"])])

    t = Table(filas, colWidths=[ANCHO_UTIL * 0.46, ANCHO_UTIL * 0.14,
                                ANCHO_UTIL * 0.22, ANCHO_UTIL * 0.18])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_BARRA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, GRIS_LINEA),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, TEXTO),
    ]))
    out += [t, Spacer(1, 4)]

    # Si la tabla no cierra en 100%, se asienta la brecha de forma expresa.
    if numerico and filas[1:] and abs(tot_pct - 100.0) > 0.01:
        brecha = round(100.0 - tot_pct, 2)
        nota = ("La estructura accionaria documentada suma %s. Existe una diferencia de %s "
                "sin identificar." % (_fmt_pct(tot_pct), _fmt_pct(brecha)))
        if brecha >= 25.0:
            nota += (" Por ser igual o mayor al umbral de 25%, se adjunta el Anexo de Análisis "
                     "Razonado en términos del Manual de Prevención de Lavado de Dinero.")
        out += [Paragraph(nota, S["justo"]), Spacer(1, 6)]

    org = D.get("organo_administracion", {})
    if org:
        pares = [("*Órgano de administración", org.get("tipo")),
                 ("Presidente", org.get("presidente")),
                 ("Secretario", org.get("secretario")),
                 ("Comisario", org.get("comisario")),
                 ("*Apoderados", ", ".join(org.get("apoderados", [])) or None)]
        out += [_campos(pares, S), Spacer(1, 4)]
        out.append(Paragraph("Fuente preferente de este apartado: poderes vigentes inscritos en "
                             "el Registro Público de Comercio. El acta constitutiva se usa como "
                             "corroboración.", S["pie"]))
    out.append(Spacer(1, 8))
    return out


def _seccion_iv(D, S):
    n = len(D.get("beneficiarios", []))
    plural = "las personas" if n != 1 else "la persona"
    decls = [
        ("Que la información asentada en el presente formato es cierta, completa y verificable, "
         "y que fue obtenida de la documentación exhibida por el cliente, en cumplimiento de los "
         "artículos 32-B Ter, 32-B Quáter y 32-B Quinquies del Código Fiscal de la Federación, "
         "las Reglas 2.8.22 a 2.8.24 de la Resolución Miscelánea Fiscal vigente y la LFPIORPI."),
        ("Que ninguna de %s identificadas en el apartado II tiene el carácter de Persona "
         "Políticamente Expuesta, conforme a la información de que dispone la sociedad." % plural),
        ("Que ha puesto a disposición de cada una de dichas personas el Aviso de Privacidad de "
         "Grit Payment Solutions, S.A.P.I. de C.V."),
    ]
    out = [_barra("IV. DECLARACIONES BAJO PROTESTA DE DECIR VERDAD", S), Spacer(1, 4)]
    out.append(Paragraph("El representante legal del cliente declara bajo protesta de decir "
                         "verdad:", S["cuerpo"]))
    out.append(Spacer(1, 3))
    for i, t in enumerate(decls, start=1):
        out.append(Paragraph("%d. %s" % (i, t), S["justo"]))
        out.append(Spacer(1, 3))
    out.append(Spacer(1, 5))
    return out


def _seccion_v(D, S):
    txt = ("Los datos personales recabados en este formato serán tratados de conformidad con el "
           "Aviso de Privacidad de Grit Payment Solutions, S.A.P.I. de C.V., con domicilio en %s, "
           "exclusivamente para el cumplimiento de las obligaciones fiscales y en materia de "
           "prevención de lavado de dinero. Son titulares de dichos datos tanto el representante "
           "legal como cada una de las personas identificadas en el apartado II." %
           DOMICILIO_RESPONSABLE)
    return [_barra("V. AVISO DE PRIVACIDAD", S), Spacer(1, 4),
            Paragraph(txt, S["justo"]), Spacer(1, 10)]


def _seccion_vi(D, S):
    rc = D.get("responsable_cumplimiento", {})
    rep = D.get("firmante_cliente", {})

    def bloque(nombre, cargo):
        return [Spacer(1, 22),
                Table([[""]], colWidths=[ANCHO_UTIL * 0.42],
                      style=TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.6, TEXTO)])),
                Spacer(1, 3),
                Paragraph((nombre or "").upper(), S["firma"]),
                Paragraph(cargo, S["firma_sub"])]

    izq = bloque(rep.get("nombre"), rep.get("cargo", "Representante Legal"))
    der = bloque(rc.get("nombre"), rc.get("cargo", "Responsable de Cumplimiento PLD"))
    t = Table([[izq, der]], colWidths=[ANCHO_UTIL / 2] * 2)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 12)]))
    return [KeepTogether([_barra("VI. FIRMAS", S), t, Spacer(1, 10)])]


def _seccion_vii(D, S):
    rc = D.get("responsable_cumplimiento", {})
    pares = [("Nombre", rc.get("nombre")),
             ("Cargo", rc.get("cargo", "Responsable de Cumplimiento / Oficial de Cumplimiento PLD")),
             ("*Empresa", rc.get("empresa", SUJETO_OBLIGADO)),
             ("Fecha de elaboración", rc.get("fecha", D["fecha_llenado"])),
             ("Lugar", rc.get("lugar", "Ciudad de México"))]
    fuentes = D.get("procedencia") or []
    if fuentes:
        nota = "Documento generado a partir de: %s." % "; ".join(fuentes)
    else:
        nota = ("Documento generado a partir de la documentación que obra en el expediente de "
                "identificación del cliente.")
    return [KeepTogether([_barra("VII. DATOS DEL RESPONSABLE DE CUMPLIMIENTO", S), Spacer(1, 4),
                          _campos(pares, S), Spacer(1, 8),
                          Paragraph(nota, S["pie"])])]


# ─────────────────────────────────────────────────────────────────────────────
# Documento
# ─────────────────────────────────────────────────────────────────────────────
def _pie_pagina(canv, doc):
    canv.saveState()
    canv.setStrokeColor(NEA_CORAL)
    canv.setLineWidth(1.2)
    canv.line(MARGEN, 12 * mm, letter[0] - MARGEN, 12 * mm)
    canv.setFont("Helvetica", 6.5)
    canv.setFillColor(colors.HexColor("#555555"))
    canv.drawString(MARGEN, 8.5 * mm, SUJETO_OBLIGADO)
    canv.drawRightString(letter[0] - MARGEN, 8.5 * mm, "Página %d" % canv.getPageNumber())
    canv.restoreState()


def _validar(D):
    if not D.get("cliente", {}).get("razon_social"):
        raise ValueError("Falta cliente.razon_social")
    if not D.get("beneficiarios"):
        raise ValueError("Debe haber al menos un beneficiario controlador, o generarse el Anexo "
                         "de Análisis Razonado en el supuesto de no identificación.")
    crit = D.get("criterio_identificacion", "participacion")
    if crit not in CRITERIOS:
        raise ValueError("criterio_identificacion inválido: %r. Válidos: %s"
                         % (crit, sorted(CRITERIOS)))
    if not D.get("fecha_llenado"):
        hoy = date.today()
        D["fecha_llenado"] = "%02d/%02d/%d" % (hoy.day, hoy.month, hoy.year)
    return D


def generar_beneficiario(datos: dict, output_path: str):
    """Genera el Formato de Identificación del Beneficiario Controlador."""
    D = _validar(dict(datos))
    S = _estilos()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = BaseDocTemplate(output_path, pagesize=letter,
                          leftMargin=MARGEN, rightMargin=MARGEN,
                          topMargin=MARGEN, bottomMargin=18 * mm,
                          title="Formato de Identificación del Beneficiario Controlador",
                          author=SUJETO_OBLIGADO)
    frame = Frame(MARGEN, 18 * mm, ANCHO_UTIL,
                  letter[1] - MARGEN - 18 * mm, id="cuerpo",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=_pie_pagina)])

    story = []
    story += _encabezado(D, S)
    story += _seccion_i(D, S)
    story += _seccion_ii(D, S)
    story += _seccion_iii(D, S)
    story += _seccion_iv(D, S)
    story += _seccion_v(D, S)
    story += _seccion_vi(D, S)
    story += _seccion_vii(D, S)

    doc.build(story)
    print("Formato de beneficiario controlador generado: %s" % output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        generar_beneficiario(json.load(fh), sys.argv[2])
