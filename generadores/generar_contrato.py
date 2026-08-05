"""
generar_contrato.py — Llenado de Carátula del Contrato de Crédito Nea Card
===========================================================================
Todas las coordenadas están PRE-MAPEADAS. No se recalcula nada.
Solo se sustituyen los valores del cliente.

Uso:
    python generar_contrato.py <datos_cliente.json> <output.pdf>

    El JSON debe tener estas claves:
    {
      "razon_social":     "EMPRESA, S.A. DE C.V.",
      "nombre_comercial": "NOMBRE CORTO",
      "rep_legal":        "APELLIDO PAT APELLIDO MAT NOMBRE",
      "rfc_empresa":      "RFC123456XXX",
      "linea_credito":    "$100,000.00 M.N.",
      "mensualidad":      "$2,000.00 M.N."
    }

Coordenadas verificadas con AC-JACARANDAS y Primeflight.
PDF base: assets/Contrato_Vacio.pdf (incluido en el skill)
Dimensiones: 612 x 792 pts (letter). y=0 en la parte INFERIOR.
"""

import io, os, sys, json
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# ─────────────────────────────────────────────────────────────────────────────
# MAPA DE CAMPOS — todas las coordenadas pre-calculadas y verificadas
# ─────────────────────────────────────────────────────────────────────────────
CAMPOS = {
    # Datos del cliente
    "razon_social":       {"x": 67,  "y": 580, "font_size": 9},
    "nombre_comercial":   {"x": 354, "y": 580, "font_size": 9},
    "rep_legal":          {"x": 67,  "y": 544, "font_size": 9},
    "rfc_empresa":        {"x": 420, "y": 544, "font_size": 9},
    # Línea de crédito — white_box tapa el "$0.00 M.N." del PDF vacío
    "linea_credito":      {"x": 434, "y": 451, "font_size": 9,
                           "white_box": {"x": 430, "y": 447, "w": 128, "h": 14}},
    # Checkbox Mensual — valor fijo, siempre X
    "checkbox_mensual":   {"x": 309, "y": 338, "font_size": 10, "bold": True,
                           "valor_fijo": "X"},
    # Mensualidad — white_box tapa el "$0.00 M.N." del PDF vacío
    "mensualidad":        {"x": 130, "y": 241, "font_size": 9,
                           "white_box": {"x": 128, "y": 235, "w": 205, "h": 18}},
    # Firma cliente
    "firma_razon_social": {"x": 152, "y": 141, "font_size": 8},
    "firma_rep_legal":    {"x": 152, "y": 131, "font_size": 8},
}


def fill_contrato(datos: dict, output_path: str, input_pdf_path: str = None):
    if input_pdf_path is None:
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        input_pdf_path = os.path.join(skill_dir, "assets", "Contrato_Vacio.pdf")

    if not os.path.exists(input_pdf_path):
        raise FileNotFoundError(f"PDF base no encontrado: {input_pdf_path}")

    # Overlay con recuadros blancos + texto
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    for campo, cfg in CAMPOS.items():
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
    print(f"Contrato generado: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        datos = json.load(f)
    fill_contrato(datos, sys.argv[2])
