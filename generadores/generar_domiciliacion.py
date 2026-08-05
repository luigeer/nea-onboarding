"""Genera la Autorización de Domiciliación (formato BanBajío) para clientes de Nea.

Llena por overlay el template oficial. El template ya trae pre-llenado:
  - Punto 1: proveedor = Grit Payment Solutions, S.A.P.I. de C.V.
  - Punto 2: bien a pagar = Tarjeta de credito corporativa
  - Punto 3: Credito Asociado a la Nomina = No (X)
  - Punto 4: dia especifico = Un dia despues de la fecha de corte
  - Punto 9: plazo indeterminado (X)

Claves del diccionario de datos:
  razon_social          str   Razon social del titular de la cuenta (obligatorio)
  representante         str   Nombre del representante legal que firma (obligatorio)
  banco                 str   Banco donde esta la cuenta a cargar (obligatorio)
  clabe                 str   CLABE 18 digitos (obligatorio si no hay tarjeta ni telefono)
  fecha                 str   Fecha del formato. Default: fecha de hoy en formato largo
  periodicidad          str   Default: "Mensual"
  tarjeta_debito        str   Opcional, 16 digitos
  telefono              str   Opcional, movil asociado a la cuenta
  opcion_cargo          str   "monto_maximo" | "pago_minimo" | "saldo_total" | "monto_fijo"
                              Default: "saldo_total" (estandar para tarjeta corporativa revolvente)
  monto                 str   Monto en pesos. Requerido si opcion_cargo es
                              "monto_maximo" o "monto_fijo"

Uso:
    python generar_domiciliacion.py datos.json salida.pdf
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
W = 612.0
FONT = "Helvetica-Bold"
SIZE = 8.0

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

OPCIONES_VALIDAS = {"monto_maximo", "pago_minimo", "saldo_total", "monto_fijo"}


def _y(line_top, offset=2.0):
    """Convierte el 'top' de pdfplumber de una linea rellenable a baseline de reportlab.

    Calibrado contra el texto pre-llenado del template: y_rl = H - line_top + 2
    """
    return H - line_top + offset


# Coordenadas calibradas sobre el template oficial.
# (x_inicio, line_top) — line_top es el 'top' de pdfplumber de la linea rellenable.
P1 = {
    "periodicidad":   (103.0, 386.8),
    "banco":          (103.0, 435.6),
    "tarjeta_debito": (237.0, 482.2),
    "clabe":          (342.0, 506.6),
    "telefono":       (276.0, 529.2),
    "monto_maximo":   (369.0, 553.7),
    "x_pago_minimo":  (205.0, 667.1),
    "x_saldo_total":  (261.0, 689.5),
    "x_monto_fijo":   (104.0, 710.2),
    "monto_fijo_val": (197.0, 710.2),
}


def _fit(c, texto, ancho, font=FONT, size=SIZE, minimo=5.5):
    """Reduce el tamano de fuente hasta que el texto quepa en 'ancho' puntos."""
    s = size
    while s > minimo and c.stringWidth(texto, font, s) > ancho:
        s -= 0.25
    return s


def _overlay_p1(d):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont(FONT, SIZE)

    # Fecha: se escribe a la derecha de la etiqueta "Fecha:", no sobre una linea.
    c.drawString(452.0, H - 116.8 - 9.0 * 0.8, d["fecha"])

    ANCHOS = {"periodicidad": 331.0, "banco": 331.0, "clabe": 154.0,
              "tarjeta_debito": 180.0, "telefono": 182.0}
    for clave in ("periodicidad", "banco", "clabe", "tarjeta_debito", "telefono"):
        val = d.get(clave)
        if val:
            x, top = P1[clave]
            c.setFont(FONT, _fit(c, str(val), ANCHOS[clave]))
            c.drawString(x, _y(top), str(val))
    c.setFont(FONT, SIZE)

    opcion = d.get("opcion_cargo", "saldo_total")
    if opcion == "monto_maximo":
        x, top = P1["monto_maximo"]
        c.drawString(x, _y(top), d["monto"])
    elif opcion == "pago_minimo":
        x, top = P1["x_pago_minimo"]
        c.drawString(x, _y(top), "X")
    elif opcion == "saldo_total":
        x, top = P1["x_saldo_total"]
        c.drawString(x, _y(top), "X")
    elif opcion == "monto_fijo":
        x, top = P1["x_monto_fijo"]
        c.drawString(x, _y(top), "X")
        x, top = P1["monto_fijo_val"]
        c.drawString(x, _y(top), d["monto"])

    c.save()
    buf.seek(0)
    return buf


def _overlay_p2(d):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    # Razon social del titular, centrada sobre la linea de firma (x 152.2..447.0)
    titular = d["razon_social"].upper()
    c.setFont(FONT, _fit(c, titular, 290.0))
    c.drawCentredString(299.6, _y(228.4, 4.0), titular)

    # Nombre del representante, a la derecha de "Representada por:"
    rep = d["representante"]
    c.setFont("Helvetica", _fit(c, rep, 180.0, font="Helvetica"))
    c.drawString(265.0, H - 247.4 - 8.2 * 0.8, rep)

    c.save()
    buf.seek(0)
    return buf


def _validar(d):
    faltantes = [k for k in ("razon_social", "representante", "banco") if not d.get(k)]
    if faltantes:
        raise ValueError(f"Faltan campos obligatorios: {', '.join(faltantes)}")

    if not any(d.get(k) for k in ("clabe", "tarjeta_debito", "telefono")):
        raise ValueError(
            "El punto 6 exige al menos un dato de identificacion de la cuenta: "
            "clabe, tarjeta_debito o telefono."
        )

    clabe = str(d.get("clabe", "")).replace(" ", "")
    if clabe:
        if not (clabe.isdigit() and len(clabe) == 18):
            raise ValueError(f"CLABE invalida: se esperan 18 digitos, se recibio '{clabe}'")
        d["clabe"] = clabe

    tarjeta = str(d.get("tarjeta_debito", "")).replace(" ", "")
    if tarjeta:
        if not (tarjeta.isdigit() and len(tarjeta) == 16):
            raise ValueError(f"Tarjeta de debito invalida: se esperan 16 digitos, se recibio '{tarjeta}'")
        d["tarjeta_debito"] = tarjeta

    opcion = d.setdefault("opcion_cargo", "saldo_total")
    if opcion not in OPCIONES_VALIDAS:
        raise ValueError(f"opcion_cargo invalida: '{opcion}'. Validas: {sorted(OPCIONES_VALIDAS)}")
    if opcion in ("monto_maximo", "monto_fijo") and not d.get("monto"):
        raise ValueError(f"opcion_cargo='{opcion}' requiere el campo 'monto'")

    d.setdefault("periodicidad", "Mensual")
    if not d.get("fecha"):
        hoy = date.today()
        d["fecha"] = f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

    return d


def generar_domiciliacion(datos: dict, output_path: str, template_path: str = None):
    """Genera la autorizacion de domiciliacion llenando el template oficial de Nea."""
    d = _validar(dict(datos))

    if template_path is None:
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(skill_dir, "assets", "Formato_Domiciliacion_Template.pdf")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template no encontrado: {template_path}")

    reader = PdfReader(template_path)
    writer = PdfWriter()
    overlays = {0: _overlay_p1(d), 1: _overlay_p2(d)}

    for i, page in enumerate(reader.pages):
        if i in overlays:
            page.merge_page(PdfReader(overlays[i]).pages[0])
        writer.add_page(page)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Domiciliacion generada: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1]) as fh:
        generar_domiciliacion(json.load(fh), sys.argv[2])
