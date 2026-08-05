# -*- coding: utf-8 -*-
"""
generar_adenda_pf.py — Adenda de Obligado Solidario, PERSONA FÍSICA
====================================================================
Variante del template de Nea para cuando el obligado solidario es persona física
y comparece por su propio derecho.

Diferencias frente a la versión de persona moral:
  - El obligado no tiene representante legal: se obliga con su patrimonio personal
  - La declaración I recaba nombre, nacionalidad, CURP, RFC, ocupación, identificación,
    domicilio, contacto y estado civil
  - Nueve cláusulas en lugar de cinco: se agregan renuncia a orden y excusión,
    autorización de buró, datos personales, notificaciones y cesión
  - Incluye Anexo A de consentimiento del cónyuge, aplicable solo bajo régimen de
    sociedad conyugal

Claves del diccionario de datos:
  fecha                    str  Default: fecha de hoy en formato largo
  cliente_razon_social     str  (obligatorio)
  cliente_rep_legal        str  (obligatorio)
  obligado                 dict (obligatorio) — ver OBLIGADO_OBLIGATORIOS
  regimen_conyugal         str  "sociedad_conyugal" | "separacion_bienes" | None
  conyuge                  dict Requerido si regimen_conyugal == "sociedad_conyugal"
  vigencia_buro_anios      int  Default 3, consistente con la política de Nea
  url_aviso                str  Default https://getnea.com/terms.html
  dias_aviso_cambio        int  Default 5
  incluir_anexo_conyuge    bool Default: True si hay cónyuge, False si no

Uso:
    python generar_adenda_pf.py datos.json salida.pdf [template.pdf]
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
SIZE = 10.5
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

OBLIGADO_OBLIGATORIOS = ("nombre", "nacionalidad", "fecha_lugar_nacimiento", "curp", "rfc",
                         "ocupacion", "id_tipo", "id_numero", "id_autoridad", "domicilio",
                         "telefono", "correo")
# estado_civil es opcional: el inciso d) del template admite quedar en blanco. Si se
# omite, no puede afirmarse que el Anexo A no aplica, así que conviene conservarlo.
CONYUGE_OBLIGATORIOS = ("nombre", "nacionalidad", "curp", "identificacion", "domicilio")


def _y(top):
    """Baseline en coordenadas reportlab para una fila del template.

    Calibrado contra la etiqueta 'Fecha:' del template: y = H - top - size*0.8
    Las líneas rellenables son corridas de guiones bajos que quedan 2 pt debajo
    de esta baseline, así que el texto se asienta justo encima.
    """
    return H - top - SIZE * 0.8


# (x_inicio, top, ancho_disponible)
P1 = {
    "fecha":                   (102.0,  72.1, 132.0),
    "cliente_razon_social":    ( 65.0, 165.1, 173.0),
    "cliente_rep_legal":       ( 65.0, 178.9, 173.0),
    "nombre":                  ( 65.0, 192.7, 173.0),
    "nacionalidad":            (279.0, 304.5,  86.0),
    "nombre_completo":         (172.0, 352.9, 202.0),
    "fecha_lugar_nacimiento":  (221.0, 370.7, 167.0),
    "curp":                    (119.0, 388.5, 144.0),
    "rfc":                     (111.0, 406.3, 149.0),
    "ocupacion":               (192.0, 424.1, 179.0),
    "id_tipo":                 (177.0, 445.9, 115.0),
    "id_numero":               (371.0, 445.9, 103.0),
    "id_autoridad":            ( 65.0, 459.7, 115.0),
    "domicilio":               ( 65.0, 508.1, 261.0),
    "telefono":                ( 65.0, 521.9, 103.0),
    "correo":                  (267.0, 521.9, 132.0),
    "estado_civil":            (182.0, 542.7, 103.0),
}

P3 = {
    "vigencia_buro_anios": (140.0, 180.7,  44.0),
    "url_aviso":           (316.0, 256.7, 132.0),
    "dias_aviso_cambio":   (127.0, 346.5,  33.0),
}

P4 = {
    "cliente_razon_social": ( 65.0, 204.5, 300.0),   # sobre "(El Cliente)"
    "cliente_rep_legal":    (155.0, 297.0, 144.0),
    "obligado_nombre":      (108.0, 429.4, 162.0),
}

P5 = {
    "conyuge_nombre":         (161.0, 146.3, 173.0),
    "conyuge_nacionalidad":   (419.0, 146.3,  86.0),
    "conyuge_curp":           (259.0, 160.1, 132.0),
    "conyuge_identificacion": ( 65.0, 173.9, 161.0),
    "conyuge_domicilio":      (317.0, 173.9, 220.0),
    "obligado_nombre":        (176.0, 208.5, 173.0),
    "conyuge_firma":          (108.0, 465.3, 161.0),
}


def _fit(c, texto, ancho, font=FONT, size=SIZE, minimo=6.5):
    s = size
    while s > minimo and c.stringWidth(texto, font, s) > ancho:
        s -= 0.25
    return s


def _poner(c, mapa, clave, valor, bold=False):
    if valor in (None, ""):
        return
    valor = str(valor)
    x, top, ancho = mapa[clave]
    fuente = FONT_BOLD if bold else FONT
    c.setFont(fuente, _fit(c, valor, ancho, font=fuente))
    c.drawString(x, _y(top), valor)


def _overlay_p1(D):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    ob = D["obligado"]
    _poner(c, P1, "fecha", D["fecha"], bold=True)
    _poner(c, P1, "cliente_razon_social", D["cliente_razon_social"])
    _poner(c, P1, "cliente_rep_legal", D["cliente_rep_legal"])
    _poner(c, P1, "nombre", ob["nombre"])
    for k in ("nacionalidad", "fecha_lugar_nacimiento", "curp", "rfc", "ocupacion",
              "id_tipo", "id_numero", "id_autoridad", "domicilio", "telefono",
              "correo", "estado_civil"):
        _poner(c, P1, k, ob.get(k))
    _poner(c, P1, "nombre_completo", ob["nombre"])
    c.save()
    buf.seek(0)
    return buf


def _overlay_p3(D):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _poner(c, P3, "vigencia_buro_anios", D["vigencia_buro_anios"])
    _poner(c, P3, "url_aviso", D["url_aviso"])
    _poner(c, P3, "dias_aviso_cambio", D["dias_aviso_cambio"])
    c.save()
    buf.seek(0)
    return buf


def _overlay_p4(D):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _poner(c, P4, "cliente_razon_social", D["cliente_razon_social"].upper(), bold=True)
    _poner(c, P4, "cliente_rep_legal", D["cliente_rep_legal"])
    _poner(c, P4, "obligado_nombre", D["obligado"]["nombre"])
    c.save()
    buf.seek(0)
    return buf


def _overlay_p5(D):
    """Anexo A. Si no hay datos de cónyuge la hoja se deja íntegramente en blanco:
    llenar solo el nombre del obligado la haría ver como un anexo a medio completar."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    cy = D.get("conyuge") or {}
    _poner(c, P5, "conyuge_nombre", cy.get("nombre"))
    _poner(c, P5, "conyuge_nacionalidad", cy.get("nacionalidad"))
    _poner(c, P5, "conyuge_curp", cy.get("curp"))
    _poner(c, P5, "conyuge_identificacion", cy.get("identificacion"))
    _poner(c, P5, "conyuge_domicilio", cy.get("domicilio"))
    _poner(c, P5, "obligado_nombre", D["obligado"]["nombre"])
    _poner(c, P5, "conyuge_firma", cy.get("nombre"))
    c.save()
    buf.seek(0)
    return buf


def _validar(D):
    for k in ("cliente_razon_social", "cliente_rep_legal"):
        if not D.get(k):
            raise ValueError("Falta campo obligatorio: %s" % k)
    ob = D.get("obligado") or {}
    faltantes = [k for k in OBLIGADO_OBLIGATORIOS if not ob.get(k)]
    if faltantes:
        raise ValueError("Faltan datos del obligado solidario: %s" % ", ".join(faltantes))

    rfc = str(ob["rfc"]).replace(" ", "").replace("-", "").upper()
    if len(rfc) != 13:
        raise ValueError(
            "RFC del obligado solidario con %d caracteres. Esta variante es para persona "
            "física (13 caracteres). Si es persona moral usa generar_adenda.py." % len(rfc))
    ob["rfc"] = rfc

    curp = str(ob["curp"]).replace(" ", "").upper()
    if len(curp) != 18:
        raise ValueError("CURP inválida: se esperan 18 caracteres, se recibió %d." % len(curp))
    ob["curp"] = curp

    # El inciso d) del template condiciona el Anexo A al régimen de sociedad conyugal.
    regimen = D.get("regimen_conyugal")
    cy = D.get("conyuge") or {}
    if regimen == "sociedad_conyugal":
        faltan_cy = [k for k in CONYUGE_OBLIGATORIOS if not cy.get(k)]
        if faltan_cy:
            raise ValueError(
                "Bajo régimen de sociedad conyugal el template exige el consentimiento del "
                "cónyuge (Anexo A). Faltan: %s" % ", ".join(faltan_cy))
    elif cy and regimen is None:
        raise ValueError("Se proporcionaron datos de cónyuge sin especificar regimen_conyugal.")

    D.setdefault("vigencia_buro_anios", 3)
    D.setdefault("url_aviso", "https://getnea.com/terms.html")
    D.setdefault("dias_aviso_cambio", 5)
    if "incluir_anexo_conyuge" not in D:
        D["incluir_anexo_conyuge"] = bool(cy)
    if not D.get("fecha"):
        hoy = date.today()
        D["fecha"] = "%d de %s de %d" % (hoy.day, MESES[hoy.month - 1], hoy.year)
    return D


def generar_adenda_pf(datos: dict, output_path: str, template_path: str = None):
    """Genera la adenda de obligado solidario persona física."""
    D = _validar(dict(datos))

    if template_path is None:
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(skill_dir, "assets",
                                     "Adenda_Obligado_Solidario_Persona_Fisica_Template.pdf")
    if not os.path.exists(template_path):
        raise FileNotFoundError("Template no encontrado: %s" % template_path)

    reader = PdfReader(template_path)
    writer = PdfWriter()
    overlays = {0: _overlay_p1(D), 2: _overlay_p3(D), 3: _overlay_p4(D)}
    # El Anexo A solo se llena si hay datos de cónyuge. Si se incluye la hoja sin
    # ellos, va íntegramente en blanco: llenar solo el nombre del obligado la haría
    # ver como un anexo a medio completar.
    if D["incluir_anexo_conyuge"] and D.get("conyuge"):
        overlays[4] = _overlay_p5(D)

    for i, page in enumerate(reader.pages):
        # El Anexo A se omite cuando no aplica: el propio template señala que
        # "si no aplica, este Anexo se tiene por no puesto".
        if i == 4 and not D["incluir_anexo_conyuge"]:
            continue
        if i in overlays:
            page.merge_page(PdfReader(overlays[i]).pages[0])
        writer.add_page(page)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    print("Adenda (persona física) generada: %s%s" % (
        output_path, "" if D["incluir_anexo_conyuge"] else "  [sin Anexo A]"))
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    tpl = sys.argv[3] if len(sys.argv) > 3 else None
    with open(sys.argv[1], encoding="utf-8") as fh:
        generar_adenda_pf(json.load(fh), sys.argv[2], tpl)
