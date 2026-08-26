"""
generar_contrato_pfae.py — Llenado de Carátula del Contrato de Crédito Nea Card (PFAE)
=========================================================================================
Mismo patrón que generar_contrato.py, sobre la plantilla de Persona Física con
Actividad Empresarial: un solo firmante (el propio cliente, no hay
representante legal de una sociedad detrás), y trae CURP en vez de una
segunda fila de datos del representante.

Uso:
    python generar_contrato_pfae.py <datos_cliente.json> <output.pdf>

    El JSON debe tener estas claves:
    {
      "nombre_pf":        "APELLIDO PAT APELLIDO MAT NOMBRE",
      "curp":              "XXXX000000XXXXXXXX",
      "nombre_comercial": "NOMBRE CORTO",
      "rfc":               "XXXX000000XXX",
      "linea_credito":    "$50,000.00 M.N.",
      "mensualidad":      "$1,050.00 M.N.",
      "firma_nombre":     "APELLIDO PAT APELLIDO MAT NOMBRE"
    }

Coordenadas verificadas contra "Contrato Credito Nea PFAE Template.pdf"
(comparadas campo por campo, con pdfplumber, contra las líneas de la propia
plantilla — no reutilizan las de generar_contrato.py: los renglones no caen
en las mismas coordenadas).
PDF base: assets/Contrato_Vacio_PFAE.pdf
Dimensiones: 612 x 792 pts (letter). y=0 en la parte INFERIOR.
"""

import io, os, sys, json
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# ─────────────────────────────────────────────────────────────────────────────
# MAPA DE CAMPOS — coordenadas verificadas contra la plantilla PFAE
# ─────────────────────────────────────────────────────────────────────────────
CAMPOS_PFAE = {
    # Datos del cliente
    "nombre_pf":          {"x": 67,  "y": 582.6, "font_size": 9},
    "curp":               {"x": 354, "y": 582.6, "font_size": 9},
    "nombre_comercial":   {"x": 67,  "y": 547.5, "font_size": 9},
    "rfc":                {"x": 420, "y": 547.5, "font_size": 9},
    # Línea de crédito — white_box tapa el "$0 M.N." del PDF vacío
    "linea_credito":      {"x": 434, "y": 451, "font_size": 9,
                           "white_box": {"x": 430, "y": 447, "w": 128, "h": 14}},
    # Checkbox Mensual — valor fijo, siempre X (mismo renglón y coordenada que
    # en generar_contrato.py: "Periodicidad: Semanal/Quincenal/Mensual" no
    # cambió de fila entre las dos plantillas)
    "checkbox_mensual":   {"x": 309, "y": 338, "font_size": 10, "bold": True,
                           "valor_fijo": "X"},
    # Mensualidad — sin white_box: en esta plantilla el renglón está
    # genuinamente en blanco, no hay "$0.00 M.N." que tapar
    "mensualidad":        {"x": 140, "y": 235, "font_size": 9},
    # Firma cliente — un solo renglón: el PFAE firma por su propio derecho
    "firma_nombre":       {"x": 100, "y": 128, "font_size": 8},
}


def fill_contrato_pfae(datos: dict, output_path: str, input_pdf_path: str = None):
    if input_pdf_path is None:
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        input_pdf_path = os.path.join(skill_dir, "assets", "Contrato_Vacio_PFAE.pdf")

    if not os.path.exists(input_pdf_path):
        raise FileNotFoundError(f"PDF base no encontrado: {input_pdf_path}")

    # Overlay con recuadros blancos + texto
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    for campo, cfg in CAMPOS_PFAE.items():
        if "white_box" in cfg:
            wb = cfg["white_box"]
            c.setFillColorRGB(1, 1, 1)
            c.setStrokeColorRGB(1, 1, 1)
            c.rect(wb["x"], wb["y"], wb["w"], wb["h"], fill=1, stroke=0)

        valor = cfg.get("valor_fijo") or datos.get(campo, "")
        if not valor:
            continue

        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold" if cfg.get("bold") else "Helvetica", cfg["font_size"])
        c.drawString(cfg["x"], cfg["y"], str(valor))

    c.save()
    buf.seek(0)

    # Merge overlay en página 1
    reader = PdfReader(input_pdf_path)
    overlay = PdfReader(buf).pages[0]
    writer = PdfWriter()
    page1 = reader.pages[0]
    page1.merge_page(overlay)
    writer.add_page(page1)
    for i in range(1, len(reader.pages)):
        writer.add_page(reader.pages[i])

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Contrato PFAE generado: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        datos = json.load(f)
    fill_contrato_pfae(datos, sys.argv[2])
