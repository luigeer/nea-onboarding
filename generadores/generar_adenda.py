"""Genera la Adenda al Contrato de Apertura de Credito en Cuenta Corriente
(Obligado Solidario) para Nea, cuando el obligado solidario es PERSONA MORAL.

El template trae pre-llenado a Nea y a su representante legal. Este script llena
los datos del Cliente y del Obligado Solidario.

Claves del diccionario de datos:
  fecha                     str  Fecha de la adenda. Default: fecha de hoy en formato largo
  cliente_razon_social      str  Razon social del Cliente (obligatorio)
  cliente_rep_legal         str  Representante legal del Cliente (obligatorio)
  obligado_razon_social     str  Razon social del Obligado Solidario (obligatorio)
  obligado_rep_legal        str  Representante legal del Obligado Solidario (obligatorio)
  obligado_rfc              str  RFC del Obligado Solidario (obligatorio)
  obligado_domicilio        str  Domicilio del Obligado Solidario (obligatorio)

NOTA: si el obligado solidario es PERSONA FISICA este template no aplica.
La declaracion I inciso a) lo describe como sociedad mercantil y el inciso b)
acredita facultades de un representante legal. Se requiere un template distinto.

Uso:
    python generar_adenda.py datos.json salida.pdf [template.pdf]
"""

import io
import json
import os
import sys
from datetime import date

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

H = 792.0
RIGHT_MARGIN = 540.0

# El template usa Roboto Light 11 en cuerpo y una bold 12 en encabezados.
# Roboto no esta disponible en el entorno; Helvetica es la sustitucion mas cercana.
BODY = "Helvetica"
BODY_SIZE = 11.0
TITLE = "Helvetica-Bold"
TITLE_SIZE = 12.0

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

OBLIGATORIOS = ("cliente_razon_social", "cliente_rep_legal", "obligado_razon_social",
                "obligado_rep_legal", "obligado_rfc", "obligado_domicilio")


def _y_linea(line_top, offset=2.0):
    """Baseline para texto que va sobre una linea rellenable."""
    return H - line_top + offset


def _y_texto(text_top, size=BODY_SIZE):
    """Baseline alineada con una fila de texto del template."""
    return H - text_top - size * 0.8


def _fit(c, texto, ancho, font=BODY, size=BODY_SIZE, minimo=7.0):
    s = size
    while s > minimo and c.stringWidth(texto, font, s) > ancho:
        s -= 0.25
    return s


# Lineas rellenables de la pagina 1: (x_inicio, line_top, ancho_disponible)
P1_LINEAS = {
    "cliente_razon_social":  ( 99.0, 240.1, 336.0),
    "cliente_rep_legal":     (165.0, 255.2, 258.0),
    "obligado_razon_social": (205.0, 270.3, 230.0),
    "obligado_rep_legal":    (163.0, 285.7, 253.0),
}

# Campos inline de las declaraciones: (x_inicio, text_top, ancho_disponible)
P1_INLINE = {
    "obligado_razon_social": (247.0, 425.3, RIGHT_MARGIN - 247.0),
    "obligado_rfc":          (111.0, 445.5, RIGHT_MARGIN - 111.0),
    "obligado_rep_legal":    (211.0, 465.9, RIGHT_MARGIN - 211.0),
}

# Bloques de firma de la pagina 3
P3 = {
    "cliente_razon_social":  ( 62.9, 400.3),   # sobre "(El Cliente)"
    "cliente_rep_legal":     (176.0, 463.0),   # tras "Representado por:"
    "obligado_razon_social": ( 62.9, 530.9),   # sobre "(El Obligado Solidario)"
    "obligado_rep_legal":    (176.0, 593.9),
}


def _overlay_p1(d):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    # Fecha, a la derecha de la etiqueta "Fecha:"
    c.setFont(TITLE, TITLE_SIZE)
    c.drawString(106.0, _y_texto(133.9, TITLE_SIZE), d["fecha"])

    for clave, (x, top, ancho) in P1_LINEAS.items():
        val = d[clave]
        c.setFont(BODY, _fit(c, val, ancho))
        c.drawString(x, _y_linea(top), val)

    for clave, (x, top, ancho) in P1_INLINE.items():
        val = d[clave]
        c.setFont(BODY, _fit(c, val, ancho))
        c.drawString(x, _y_texto(top), val)

    # Domicilio: cabe tras el "en:" o baja a la fila libre de abajo
    dom = d["obligado_domicilio"]
    c.setFont(BODY, BODY_SIZE)
    if c.stringWidth(dom, BODY, BODY_SIZE) <= RIGHT_MARGIN - 282.0:
        c.drawString(282.0, _y_texto(521.3), dom)
    else:
        c.drawString(62.9, _y_texto(541.4), dom)
        if c.stringWidth(dom, BODY, BODY_SIZE) > RIGHT_MARGIN - 62.9:
            c.setFont(BODY, _fit(c, dom, RIGHT_MARGIN - 62.9))
            c.drawString(62.9, _y_texto(541.4), dom)

    c.save()
    buf.seek(0)
    return buf


def _overlay_p3(d):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    for clave in ("cliente_razon_social", "obligado_razon_social"):
        x, top = P3[clave]
        val = d[clave].upper()
        c.setFont(TITLE, _fit(c, val, RIGHT_MARGIN - x, font=TITLE, size=TITLE_SIZE))
        c.drawString(x, _y_texto(top, TITLE_SIZE), val)

    for clave in ("cliente_rep_legal", "obligado_rep_legal"):
        x, top = P3[clave]
        val = d[clave]
        c.setFont(TITLE, _fit(c, val, RIGHT_MARGIN - x, font=TITLE, size=TITLE_SIZE))
        c.drawString(x, _y_texto(top, TITLE_SIZE), val)

    c.save()
    buf.seek(0)
    return buf


def _validar(d):
    faltantes = [k for k in OBLIGATORIOS if not d.get(k)]
    if faltantes:
        raise ValueError("Faltan campos obligatorios: %s" % ", ".join(faltantes))

    rfc = str(d["obligado_rfc"]).replace(" ", "").replace("-", "").upper()
    if len(rfc) != 12:
        raise ValueError(
            "RFC del obligado solidario con %d caracteres. Este template es para persona "
            "moral (12 caracteres). Si es persona fisica se requiere la variante." % len(rfc)
        )
    d["obligado_rfc"] = rfc

    if not d.get("fecha"):
        hoy = date.today()
        d["fecha"] = "%d de %s de %d" % (hoy.day, MESES[hoy.month - 1], hoy.year)
    return d


def generar_adenda(datos: dict, output_path: str, template_path: str = None):
    """Genera la adenda de obligado solidario persona moral."""
    d = _validar(dict(datos))

    if template_path is None:
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(skill_dir, "assets", "Adenda_Obligado_Solidario_Template.pdf")
    if not os.path.exists(template_path):
        raise FileNotFoundError("Template no encontrado: %s" % template_path)

    reader = PdfReader(template_path)
    writer = PdfWriter()
    overlays = {0: _overlay_p1(d), 2: _overlay_p3(d)}

    for i, page in enumerate(reader.pages):
        if i in overlays:
            page.merge_page(PdfReader(overlays[i]).pages[0])
        writer.add_page(page)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    print("Adenda generada: %s" % output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    tpl = sys.argv[3] if len(sys.argv) > 3 else None
    with open(sys.argv[1]) as fh:
        generar_adenda(json.load(fh), sys.argv[2], tpl)
