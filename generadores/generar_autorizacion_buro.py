# -*- coding: utf-8 -*-
"""
generar_autorizacion_buro.py — Autorización para solicitar reportes de crédito
==============================================================================
El formato con el que el cliente autoriza a Grit Payment Solutions a consultar
su historial en las Sociedades de Información Crediticia. Reproduce el formato
que Nea ya usaba (el mismo texto, la misma vigencia de 3 años, las mismas tres
casillas PF / PFAE / PM y el recuadro de uso exclusivo para la consulta).

No se sobrepone a un template: el formato viejo solo existía lleno, a nombre de
otros clientes, así que se construye completo aquí.

Uso:
    python generar_autorizacion_buro.py <datos.json> <salida.pdf>

Claves del diccionario: tipo_persona ("pf" | "pfae" | "pm"), solicitante,
rep_legal, rfc, domicilio, colonia, municipio, estado, cp, telefono, correo,
fecha.
"""

import json
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

EMPRESA = "GRIT PAYMENT SOLUTIONS S.A.P.I. DE C.V."
GRIS = colors.HexColor("#EFEFEF")
LINEA = colors.HexColor("#808080")
MARGEN = 22 * mm
ANCHO = letter[0] - 2 * MARGEN

TEXTO_1 = ("Por este conducto autorizo expresamente a <b>%s</b> para que por conducto de "
           "sus funcionarios facultados lleve a cabo Investigaciones, sobre mi "
           "comportamiento crediticio o el de la Empresa que represento en Trans Union de "
           "México, S. A. SIC y/o Dun &amp; Bradstreet, S.A. SIC" % EMPRESA)
TEXTO_2 = ("Así mismo, declaro que conozco la naturaleza y alcance de la información que se "
           "solicitará, del uso que <b>%s</b>, hará de tal información y de que ésta podrá "
           "realizar consultas periódicas sobre mi historial o el de la empresa que "
           "represento, consintiendo que esta autorización se encuentre vigente por un "
           "período de 3 años contados a partir de su expedición y en todo caso durante el "
           "tiempo que se mantenga la relación jurídica." % EMPRESA)
TEXTO_3 = ("En caso de que la solicitante sea una Persona Moral, declaro bajo protesta de "
           "decir verdad Ser Representante Legal de la empresa mencionada en esta "
           "autorización; manifestando que a la fecha de firma de la presente autorización "
           "los poderes no me han sido revocados, limitados, ni modificados en forma alguna.")
TEXTO_4 = ("<b>Estoy de acuerdo y acepto que este documento quede bajo propiedad de %s y/o "
           "Sociedad de Información Crediticia consultada para efectos de control y "
           "cumplimiento del artículo 28 de la Ley para Regular a Las Sociedades de "
           "Información Crediticia; mismo que señala que las Sociedades sólo podrán "
           "proporcionar información a un Usuario, cuando éste cuente con la autorización "
           "expresa del Cliente mediante su firma autógrafa.</b>" % EMPRESA)


def _estilos():
    base = dict(fontName="Helvetica", fontSize=9.5, leading=12.5)
    return {
        "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=10.5,
                                 leading=13, alignment=TA_CENTER),
        "cuerpo": ParagraphStyle("c", alignment=TA_JUSTIFY, **base),
        "etiqueta": ParagraphStyle("e", **base),
        "valor": ParagraphStyle("v", fontName="Helvetica", fontSize=9, leading=11),
        "centro": ParagraphStyle("x", alignment=TA_CENTER, **base),
    }


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _renglon(etiqueta, valor, S, ancho_etiqueta=38 * mm):
    """Etiqueta a la izquierda y el valor sobre una línea, como en el formato."""
    t = Table([[Paragraph(etiqueta, S["etiqueta"]), Paragraph(_esc(valor), S["valor"])]],
              colWidths=[ancho_etiqueta, ANCHO - ancho_etiqueta])
    t.setStyle(TableStyle([
        ("LINEBELOW", (1, 0), (1, 0), 0.5, LINEA),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _linea(valor, S):
    """Un valor sobre una línea de ancho completo, sin etiqueta a la izquierda."""
    t = Table([[Paragraph(_esc(valor), S["valor"])]], colWidths=[ANCHO])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.5, LINEA),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _casillas(tipo, S):
    def x(clave):
        return "<b>[ X ]</b>" if tipo == clave else "[&nbsp;&nbsp;&nbsp;]"
    texto = ("<b>Persona Física (PF)</b> %s &nbsp;&nbsp; <b>Persona Física con Actividad "
             "Empresarial (PFAE)</b> %s &nbsp;&nbsp; <b>Persona Moral (PM)</b> %s"
             % (x("pf"), x("pfae"), x("pm")))
    return Paragraph(texto, S["etiqueta"])


def _recuadro_uso_exclusivo(S):
    filas = [[Paragraph("<b>Para uso exclusivo de la Empresa que efectúa la consulta %s</b>"
                        % EMPRESA, S["etiqueta"])],
             [Paragraph("Fecha de Consulta BC : ____________________", S["etiqueta"])],
             [Paragraph("Folio de Consulta BC : ____________________", S["etiqueta"])]]
    t = Table(filas, colWidths=[ANCHO])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINEA),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINEA),
        ("BACKGROUND", (0, 0), (-1, -1), GRIS),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def generar_autorizacion_buro(D, ruta_salida):
    S = _estilos()
    doc = SimpleDocTemplate(ruta_salida, pagesize=letter, leftMargin=MARGEN,
                            rightMargin=MARGEN, topMargin=20 * mm, bottomMargin=18 * mm,
                            title="Autorización para solicitar Reportes de Crédito")
    moral = D.get("tipo_persona") == "pm"
    h = [
        Paragraph("Autorización para solicitar Reportes de Crédito<br/>"
                  "Personas Físicas / Personas Morales", S["titulo"]),
        Spacer(1, 6 * mm),
        Paragraph(TEXTO_1, S["cuerpo"]), Spacer(1, 3 * mm),
        Paragraph(TEXTO_2, S["cuerpo"]),
        Paragraph(TEXTO_3, S["cuerpo"]), Spacer(1, 4 * mm),
        Paragraph("Autorización para:", S["etiqueta"]), Spacer(1, 1 * mm),
        _casillas(D.get("tipo_persona"), S), Spacer(1, 5 * mm),
        Paragraph("Nombre del solicitante (Persona Física o Razón Social de la Persona Moral):",
                  S["etiqueta"]),
        _linea(D.get("solicitante"), S),
        Spacer(1, 2 * mm),
        _renglon("Para el caso de Persona Moral, nombre del Representante Legal:",
                 D.get("rep_legal") if moral else "", S, ancho_etiqueta=100 * mm),
        Spacer(1, 3 * mm),
        _renglon("RFC:", D.get("rfc"), S),
        _renglon("Domicilio:", D.get("domicilio"), S),
        _renglon("Colonia:", D.get("colonia"), S),
        _renglon("Municipio:", D.get("municipio"), S),
        _renglon("Estado:", D.get("estado"), S),
        _renglon("Código postal:", D.get("cp"), S),
        _renglon("Teléfono(s):", D.get("telefono"), S),
        _renglon("Fecha en que se firma la autorización:", D.get("fecha"), S,
                 ancho_etiqueta=62 * mm),
        _renglon("Mail Representante Legal:" if moral else "Mail:", D.get("correo"), S,
                 ancho_etiqueta=45 * mm),
        Spacer(1, 5 * mm),
        Paragraph(TEXTO_4, S["cuerpo"]),
        Spacer(1, 16 * mm),
        Paragraph("_______________________________________________", S["centro"]),
        Paragraph("Nombre y Firma de PF, PFAE, Representante Legal de la empresa", S["centro"]),
        Spacer(1, 8 * mm),
        _recuadro_uso_exclusivo(S),
    ]
    doc.build(h)
    return ruta_salida


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python generar_autorizacion_buro.py <datos.json> <salida.pdf>")
    with open(sys.argv[1], encoding="utf-8") as fh:
        generar_autorizacion_buro(json.load(fh), sys.argv[2])
