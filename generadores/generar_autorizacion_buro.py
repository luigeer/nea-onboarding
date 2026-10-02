"""Genera la Autorización para solicitar Reportes de Crédito (persona moral).

Es el formato con el que el cliente autoriza a Grit Payment Solutions a
consultarlo en la Sociedad de Información Crediticia. Llena por overlay la
plantilla en blanco; la "X" de Persona Moral ya viene impresa en ella, por eso
este generador solo sirve para personas morales.

La plantilla trae campos de formulario. Se escribe encima de su posición y se
quitan, para que el PDF firmado no quede editable: una autorización de buró con
un dato que se puede cambiar después de firmada no le sirve a nadie en una
auditoría.

Claves del diccionario de datos:
  razon_social          str   Razón social del cliente
  representante         str   Nombre del representante legal que firma
  rfc                   str   RFC de la persona moral
  domicilio             str   Calle, número exterior e interior
  colonia               str
  municipio             str
  estado                str
  cp                    str
  telefono              str
  fecha                 str   Fecha de firma en formato largo
  correo_representante  str

Uso:
    python generar_autorizacion_buro.py datos.json salida.pdf
"""

import io
import json
import os
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.pdfgen import canvas

FONT = "Helvetica"
SIZE = 9.0

# campo -> (x, y de la base del texto, ancho disponible hasta el fin de la línea)
# Sale del /Rect de cada campo de la plantilla; el ancho llega hasta donde
# termina el renglón impreso, que es más largo que el campo.
POSICIONES = {
    "razon_social":         (87.0, 480.5, 410.0),
    "representante":        (87.0, 449.5, 410.0),
    "rfc":                  (111.0, 423.5, 235.0),
    "domicilio":            (123.0, 408.5, 222.0),
    "colonia":              (119.0, 393.5, 227.0),
    "municipio":            (128.0, 376.5, 105.0),
    "estado":               (283.0, 376.5, 124.0),
    "cp":                   (115.0, 364.5, 100.0),
    "telefono":             (140.0, 348.5, 206.0),
    "fecha":                (245.0, 336.5, 104.0),
    "correo_representante": (194.0, 322.5, 300.0),
}


def _fit(c, texto, ancho, minimo=5.5):
    """Reduce el tamaño de fuente hasta que el texto quepa en 'ancho' puntos."""
    s = SIZE
    while s > minimo and c.stringWidth(texto, FONT, s) > ancho:
        s -= 0.25
    return s


def _overlay(d, ancho_pag, alto_pag):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(ancho_pag, alto_pag))
    for clave, (x, y, ancho) in POSICIONES.items():
        valor = str(d.get(clave) or "")
        if valor:
            c.setFont(FONT, _fit(c, valor, ancho))
            c.drawString(x, y, valor)
    c.save()
    buf.seek(0)
    return buf


def generar_autorizacion_buro(datos, output_path, template_path=None):
    if template_path is None:
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(raiz, "assets", "Autorizacion_Buro_PM_Template.pdf")
    if not os.path.exists(template_path):
        raise FileNotFoundError("Template no encontrado: %s" % template_path)

    reader = PdfReader(template_path)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i == 0:
            caja = page.mediabox
            page.merge_page(PdfReader(_overlay(datos, float(caja.width),
                                               float(caja.height))).pages[0])
        if "/Annots" in page:
            del page[NameObject("/Annots")]
        writer.add_page(page)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    print("Autorización de buró generada: %s" % output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        generar_autorizacion_buro(json.load(fh), sys.argv[2])
