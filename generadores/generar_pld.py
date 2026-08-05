"""
generar_pld.py — Generación del Formato PLD (Persona Moral) Nea Card
=====================================================================
Genera el PDF desde cero con reportlab. Todas las posiciones, fuentes
y textos fijos están pre-definidos. Solo se sustituyen los datos del cliente.

Uso:
    python generar_pld.py <datos_cliente.json> <output.pdf>

    El JSON debe tener estas claves:
    {
      "fecha_operacion":      "24/03/2026",
      "razon_social":         "EMPRESA, S.A. DE C.V.",
      "fecha_constitucion":   "31/08/2012",
      "pais_nacionalidad":    "México",
      "rfc_empresa":          "RFC123456XXX",
      "actividad_giro":       "Venta de combustibles automotrices",
      "calle":                "AV. GOBERNADORES",
      "num_ext":              "46",
      "colonia":              "BURÓCRATAS",
      "cp":                   "39090",
      "municipio":            "CHILPANCINGO DE LOS BRAVO",
      "estado":               "GUERRERO",
      "pais_domicilio":       "México",
      "telefono":             "7471162651",
      "correo":               "correo@empresa.mx",
      "nombre_rep":           "APELLIDO_PAT APELLIDO_MAT NOMBRE",
      "fecha_nac_rep":        "07/07/1951",
      "pais_nac_rep":         "México",
      "pais_nacionalidad_rep":"México",
      "curp_rep":             "XXXX000000XXXXXXXX",
      "rfc_rep":              "XXXX000000XXX",
      "tipo_id":              "INE - Credencial para votar",
      "num_id":               "1234567890",
      "autoridad_emisora":    "Instituto Nacional Electoral (INE)",
      "pais_emisor":          "México",
      "quien_lleno":          "Luis Gomez Montijano",
      "comprobante_tipo":     "telefono",   <- "agua" | "luz" | "telefono"
      "poder_tipo":           "testimonio", <- "testimonio" | "copia_certificada"
      "tipo_id_oficial":      "ine",        <- "ine" | "pasaporte" | "cedula" | "licencia"
      "firma_razon_social":   "EMPRESA, S.A. DE C.V.",   # clave consistente con generar_contrato.py
      "firma_rep_legal":      "NOMBRE APELLIDO PAT APELLIDO MAT"  # clave consistente con generar_contrato.py
    }
"""

import os, sys, json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

W, H = letter   # 612 x 792 pts
ML = 50         # margen izquierdo
MR = 562        # margen derecho
MT = 750        # top inicial

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def sf(c, size, bold=False):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)

def line(c, x1, y, x2, width=0.5):
    c.setStrokeColor(colors.black)
    c.setLineWidth(width)
    c.line(x1, y, x2, y)

def black_bar(c, y, text, font_size=8):
    c.setFillColor(colors.black)
    c.rect(ML - 2, y - 2, MR - ML + 4, 14, fill=1, stroke=0)
    c.setFillColor(colors.white)
    sf(c, font_size, bold=True)
    c.drawCentredString(W / 2, y + 1, text)
    c.setFillColor(colors.black)

def checkbox(c, x, y, checked=False, size=10, restore_font_size=7.5):
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.rect(x, y - 1, size, size, fill=0, stroke=1)
    if checked:
        sf(c, size + 1, bold=True)
        c.setFillColor(colors.black)
        c.drawString(x + 1, y, "X")
        sf(c, restore_font_size)  # restore font after drawing X


# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA 1
# ─────────────────────────────────────────────────────────────────────────────
def page1(c, D):
    y = MT

    # Encabezado
    sf(c, 7, bold=True)
    c.drawCentredString(W/2, y, "ANEXO 4 DEL ACUERDO 02/2013 POR EL QUE SE EMITEN LAS REGLAS DE CARÁCTER GENERAL A QUE SE REFIERE LA LEY FEDERAL")
    y -= 10
    c.drawCentredString(W/2, y, "PARA LA PREVENCIÓN E IDENTIFICACIÓN DE OPERACIONES CON RECURSOS DE PROCEDENCIA ILÍCITA")
    y -= 12
    sf(c, 7)
    c.drawCentredString(W/2, y, "DATOS Y DOCUMENTOS DE IDENTIFICACIÓN DE LOS CLIENTES DE QUIENES REALICEN ACTIVIDADES VULNERABLES, RESPECTO DE")
    y -= 9
    c.drawCentredString(W/2, y, "AQUELLOS QUE SEAN PERSONAS MORALES DE NACIONALIDAD MEXICANA.")
    y -= 14
    sf(c, 8, bold=True)
    c.drawCentredString(W/2, y, "FORMULARIO DE IDENTIFICACIÓN DEL CLIENTE/USUARIO")
    y -= 10
    c.drawCentredString(W/2, y, "(PERSONAS MORALES NACIONALES     )")
    y -= 10
    sf(c, 8)
    c.setFillColor(colors.HexColor("#C0392B"))
    c.drawCentredString(W/2, y, "GRIT PAYMENT SOLUTIONS, S.A.P.I. DE C.V.")
    y -= 9
    c.drawCentredString(W/2, y, "Calle 3 Picos 65, Polanco V Seccion, Miguel Hidalgo, Ciudad de México, México CP 11560")
    c.setFillColor(colors.black)
    y -= 16

    # Fecha operación y actividad
    sf(c, 7.5)
    c.drawString(330, y, f"Fecha de la operación (dd/mm/aa): {D['fecha_operacion']}")
    y -= 10
    c.drawString(262, y, "Actividad Vulnerable que se pretende realizar: Emisión de Tarjetas de Servicio")
    y -= 16

    # ── SECCIÓN I ─────────────────────────────────────────────────────────────
    sf(c, 8, bold=True)
    c.drawString(ML, y, "I. INFORMACIÓN GENERAL")
    y -= 10
    sf(c, 7.5)
    c.drawString(ML, y, "DENOMINACIÓN O RAZÓN SOCIAL:  ")
    sf(c, 8, bold=True)
    c.drawString(ML + 148, y, D["razon_social"])
    sf(c, 7.5)
    line(c, ML, y - 2, MR)
    y -= 12

    c.drawString(ML, y, f"Fecha de Constitución [día/mes/año]: {D['fecha_constitucion']}")
    c.drawString(310, y, f"País de Nacionalidad:  {D['pais_nacionalidad']}")
    line(c, ML, y - 2, MR)
    y -= 12

    c.drawString(ML, y, f"RFC:  {D['rfc_empresa']}")
    line(c, ML, y - 2, MR)
    y -= 12

    c.drawString(ML, y, "Actividad, giro mercantil u objeto social:  ")
    sf(c, 7.5, bold=True)
    c.drawString(ML + 212, y, D["actividad_giro"])
    sf(c, 7.5)
    line(c, ML, y - 2, MR)
    y -= 18

    # ── SECCIÓN II ────────────────────────────────────────────────────────────
    sf(c, 8, bold=True)
    c.drawString(ML, y, "II.   DATOS DE CONTACTO DOMICILIO FISCAL")
    y -= 14
    sf(c, 7.5)

    c.drawString(ML, y, "Calle:")
    line(c, ML + 28, y - 2, 280)
    c.drawString(ML + 30, y, D["calle"])
    c.drawString(290, y, "No. Exterior/Interior:")
    line(c, 365, y - 2, MR)
    c.drawString(366, y, D["num_ext"])
    y -= 14

    c.drawString(ML, y, "Colonia:")
    line(c, ML + 38, y - 2, 280)
    c.drawString(ML + 40, y, D["colonia"])
    c.drawString(290, y, "C.P.:")
    line(c, 310, y - 2, MR)
    c.drawString(312, y, D["cp"])
    y -= 14

    c.drawString(ML, y, "Del. o Mpio.:")
    line(c, ML + 55, y - 2, 280)
    c.drawString(ML + 57, y, D["municipio"])
    c.drawString(290, y, "Estado.:")
    line(c, 322, y - 2, MR)
    c.drawString(324, y, D["estado"])
    y -= 14

    c.drawString(ML, y, "País:")
    line(c, ML + 22, y - 2, MR)
    c.drawString(ML + 24, y, D["pais_domicilio"])
    y -= 14

    c.drawString(ML, y, "Teléfono [clave de larga distancia y, en su caso extensión]:")
    line(c, 242, y - 2, 440)
    c.drawString(244, y, D["telefono"])
    c.drawString(445, y, "Correo")
    y -= 12
    c.drawString(ML, y, "electrónico:")
    line(c, ML + 52, y - 2, MR)
    c.drawString(ML + 54, y, D["correo"])
    y -= 18

    # ── SECCIÓN III ───────────────────────────────────────────────────────────
    sf(c, 8, bold=True)
    c.drawString(ML, y, "III. DATOS DEL REPRESENTANTE O APODERADO LEGAL")
    y -= 14
    sf(c, 7.5)
    c.drawString(ML, y, "NOMBRE COMPLETO [Apellido paterno, apellido materno y nombre(s) (sin abreviaturas)]:")
    sf(c, 8, bold=True)
    c.drawString(ML + 374, y, D["nombre_rep"])
    sf(c, 7.5)
    line(c, ML, y - 2, MR)
    y -= 14

    c.drawString(ML, y, f"Fecha de Nacimiento [día/mes/año]:  {D['fecha_nac_rep']}")
    c.drawString(310, y, f"País de Nacimiento:  {D['pais_nac_rep']}")
    y -= 16

    c.drawString(ML, y, "País de Nacionalidad:")
    line(c, ML, y - 2, 255)
    c.drawString(ML + 90, y, D["pais_nacionalidad_rep"])
    c.drawString(310, y, f"CURP:  {D['curp_rep']}")
    y -= 14
    c.drawString(310, y, f"RFC:  {D['rfc_rep']}")
    line(c, ML, y - 2, 255)
    y -= 18

    # ── SECCIÓN IV ────────────────────────────────────────────────────────────
    sf(c, 8, bold=True)
    c.drawString(ML, y, "IV. DATOS DE IDENTIFICACIÓN DEL REPRESENTANTE O APODERADO LEGAL PROPORCIONAR")
    y -= 10
    c.drawString(ML, y, "LOS SIGUIENTES DATOS DE ALGUNA IDENTIFICACIÓN OFICIAL:")
    y -= 14
    sf(c, 7.5)

    c.drawString(ML, y, f"Tipo de identificación [nombre como se indica en la identificación]:  {D['tipo_id']}")
    line(c, ML, y - 2, MR)
    y -= 14
    c.drawString(ML, y, f"Número de la identificación:  {D['num_id']}")
    line(c, ML, y - 2, MR)
    y -= 14
    c.drawString(ML, y, f"Autoridad emisora:  {D['autoridad_emisora']}")
    line(c, ML, y - 2, MR)
    y -= 14
    c.drawString(ML, y, f"País emisor:  {D['pais_emisor']}")
    line(c, ML, y - 2, MR)
    y -= 14
    c.drawString(ML, y, "Nombre, firma y cargo de la persona que llenó el presente formulario")
    y -= 10
    sf(c, 8)
    c.drawString(ML, y, D["quien_lleno"])
    y -= 12

    black_bar(c, y, "Documentos de identificación tratándose de personas morales nacionales")
    y -= 18

    # Documentación requerida
    sf(c, 8, bold=True)
    c.drawString(ML, y, "Incluir copia de la siguiente documentación:")
    y -= 14
    sf(c, 7.5)
    c.drawString(ML, y, "i)  Testimonio o copia certificada de la constitución e inscripción en el Registro Público De La Propiedad")
    y -= 14
    c.drawString(ML, y, "ii)  Cédula de Identificación Fiscal expedida por el SAT, cuando el Cliente o Usuario cuente con ellas.")
    y -= 12
    c.drawString(ML, y, "Se obtuvo constancia de Cédula de Identificación:")
    y -= 10
    c.drawString(ML, y, "SI")
    checkbox(c, ML + 12, y, checked=True)   # siempre SI
    c.drawString(ML + 28, y, "NO")
    checkbox(c, ML + 40, y, checked=False)
    y -= 18

    sf(c, 7.5)  # reset to normal (was bold from "Incluir copia" header)
    c.drawString(ML, y, "iii)  Comprobante de domicilio (vigencia no mayor a 3 meses)")
    y -= 14

    # Posiciones exactas calculadas con reportlab stringWidth a font 7.5
    tipo_comp = D.get("comprobante_tipo", "telefono").lower()
    c.drawString(50,  y, "Agua");     checkbox(c, 70,  y, checked=(tipo_comp == "agua"))
    c.drawString(88,  y, "Luz");      checkbox(c, 102, y, checked=(tipo_comp == "luz"))
    c.drawString(120, y, "Teléfono"); checkbox(c, 151, y, checked=(tipo_comp == "telefono"))
    y -= 18

    sf(c, 7.5)
    c.drawString(ML, y, "iv)  Testimonio o copia certificada del instrumento del poder del representante legal o apoderado.")
    y -= 14

    tipo_poder = D.get("poder_tipo", "testimonio").lower()
    c.drawString(50,  y, "Testimonio");       checkbox(c, 89,  y, checked=(tipo_poder == "testimonio"))
    c.drawString(107, y, "Copia certificada"); checkbox(c, 165, y, checked=(tipo_poder == "copia_certificada"))
    c.drawString(183, y, "No aportó:");       checkbox(c, 220, y, checked=(tipo_poder == "no_aporto"))
    y -= 18

    sf(c, 7.5)
    c.drawString(ML, y, "v)  Identificación oficial vigente (con fotografía) del represente legal o apoderado")
    y -= 14

    tipo_id = D.get("tipo_id_oficial", "ine").lower()
    c.drawString(50,  y, "IFE");                   checkbox(c, 64,  y, checked=(tipo_id == "ine"))
    c.drawString(82,  y, "PASAPORTE");              checkbox(c, 130, y, checked=(tipo_id == "pasaporte"))
    c.drawString(148, y, "CEDULA PROFESIONAL");     checkbox(c, 235, y, checked=(tipo_id == "cedula"))
    c.drawString(253, y, "LICENCIA");               checkbox(c, 290, y, checked=(tipo_id == "licencia"))
    c.drawString(308, y, "DOCUMENTO MIGRATORIO");   checkbox(c, 410, y, checked=(tipo_id == "migratorio"))


# ─────────────────────────────────────────────────────────────────────────────
# Declaración del cliente sobre beneficiario controlador
# ─────────────────────────────────────────────────────────────────────────────
# Leyendas textuales del Manual GRIT, apartado 8.4.11. Se asientan en la Hoja de
# Datos Generales cuando el cliente declara no conocer al beneficiario controlador.
LEYENDA_NO_CONOCE = {
    "moral": ("Declaro, bajo protesta de decir verdad, no tener conocimiento de la existencia de un "
              "Dueño Beneficiario/Beneficiario Controlador ya que mi representada es quien obtiene "
              "el beneficio."),
    "fisica": ("Declaro, bajo protesta de decir verdad, no tener conocimiento de la existencia de un "
               "Dueño Beneficiario/Beneficiario Controlador ya que actuó a cuenta propia y no a "
               "favor de terceros."),
}


def _wrap(c, texto, ancho, font="Helvetica", size=7.5):
    """Parte un texto en lineas que caben en 'ancho' puntos."""
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if c.stringWidth(prueba, font, size) <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def bloque_declaracion_bc(c, D, y):
    """Asienta la declaracion del cliente sobre el beneficiario controlador.

    Claves que consume:
      bc_declaracion   "conoce" | "no_conoce"   (default "no_conoce")
      tipo_persona     "moral" | "fisica"       (default "moral")
      bc_cantidad      int, solo si declara conocer
      cargo_rep        str, cargo del firmante   (default "Representante Legal")
    """
    decl = D.get("bc_declaracion", "no_conoce")
    tipo = D.get("tipo_persona", "moral")
    ancho = MR - ML

    sf(c, 8, bold=True)
    c.drawString(ML, y, "Declaración del Cliente")
    y -= 12

    sf(c, 7.5)
    if decl == "no_conoce":
        texto = LEYENDA_NO_CONOCE.get(tipo, LEYENDA_NO_CONOCE["moral"])
        for ln in _wrap(c, '"' + texto + '"', ancho):
            c.drawString(ML, y, ln)
            y -= 10
    else:
        n = D.get("bc_cantidad")
        detalle = ("de %s persona(s) física(s)" % n) if n else "de una o más personas físicas"
        texto = ("Declaro, bajo protesta de decir verdad, tener conocimiento de la existencia %s "
                 "con la calidad de Dueño Beneficiario/Beneficiario Controlador, cuyos datos de "
                 "identificación se asientan en el Formato de Identificación del Beneficiario "
                 "Controlador que forma parte de este expediente." % detalle)
        for ln in _wrap(c, '"' + texto + '"', ancho):
            c.drawString(ML, y, ln)
            y -= 10

    y -= 12
    line(c, ML, y, ML + 260)
    y -= 10
    sf(c, 7)
    c.drawString(ML, y, "Nombre, cargo y firma del representante legal o cliente por propio derecho")
    y -= 10
    sf(c, 8, bold=True)
    c.drawString(ML, y, D.get("firma_rep_legal", ""))
    sf(c, 7)
    cargo = D.get("cargo_rep", "Representante Legal")
    c.drawString(ML + 200, y, cargo)
    y -= 16
    sf(c, 7.5)
    return y


# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA 2
# ─────────────────────────────────────────────────────────────────────────────
def page2(c, D):
    y = MT

    black_bar(c, y, "Constancia de la existencia de algún beneficiario controlador")
    y -= 20

    sf(c, 7.5)
    c.drawString(ML, y, "vi)  Constancia por la que se acredite que quien realice la Actividad Vulnerable solicitó a su Cliente o Usuario información acerca de si tiene conocimiento")
    y -= 10
    c.drawString(ML + 20, y, "de la existencia del Dueño Beneficiario, la cual deberá estar firmada por los que participen directamente en el acto u operación.")
    y -= 14

    c.drawString(ML, y, "Se obtuvo comprobante conocimiento de existencia (cliente):")
    y -= 12
    # La constancia es esta hoja, firmada por el representante legal al final del
    # formato. Por defecto SI; se puede forzar con la clave "constancia_obtenida".
    obtenida = D.get("constancia_obtenida", True)
    c.drawString(ML, y, "SI")
    checkbox(c, ML + 12, y, checked=bool(obtenida))
    c.drawString(ML + 28, y, "NO")
    checkbox(c, ML + 40, y, checked=not bool(obtenida))
    y -= 22

    y = bloque_declaracion_bc(c, D, y)

    for txt in [
        "En el supuesto en que la persona física manifieste que sí tiene conocimiento de la existencia del Dueño Beneficiario, quien realice la Actividad Vulnerable",
        "deberá identificarlo de conformidad a lo dispuesto en la fracción VII del artículo 12 de las Reglas de Carácter General a que se refiere la Ley Federal",
        "para la Prevención e Identificación de Operaciones con Recursos de Procedencia Ilícita, cuando dicho Cliente o Usuario cuente con dicha información.",
        "",
        "Tratándose del dueño beneficiario, quienes realicen Actividades Vulnerables asentarán y recabarán los mismos datos y documéntenos que los",
        "establecidos en los Anexos, 3, 4, 4 Bis, 5, 6, 6 Bis, u 8 de las Reglas, establecidos en el presente Manual, según corresponda, en caso de que el Cliente",
        "o Usuario cuenta con ellos.",
    ]:
        c.drawString(ML, y, txt)
        y -= 10
    y -= 4

    black_bar(c, y, "AVISO DE PRIVACIDAD – PROTECCIÓN DE DATOS PERSONALES")
    y -= 18

    sf(c, 7)
    aviso = [
        "Grit Payment Solutions, S.A.P.I. de C.V., con domicilio en Calle 3 Picos 65, Polanco V Seccion, Miguel Hidalgo, Ciudad de México, México, CP 11560,",
        "es responsable de recabar sus datos personales, del uso que se le dé a los mismos y de su protección. Su información personal será utilizada para",
        "concretar la actividad que se señala al inicio del presente formato, así como para informarle sobre algún cambio o circunstancia que sea de su interés",
        "y evaluar la calidad del servicio que le brindamos. Lo anterior, en cumplimiento de lo dispuesto por la Ley Federal para la Prevención e Identificación de",
        "Operaciones con Recursos de Procedencia Ilícita, publicada en el Diario Oficial de la Federación el 17 de octubre de 2012. La información proporcionada",
        "en dicho formulario, será empleada únicamente para efecto de cumplir con lo que dispone la citada Ley en cuanto a identificación de las personas con",
        "las que se realicen Actividades consideradas como Vulnerables, así como para la presentación de avisos ante la autoridad competente en los casos",
        "específicos que la propia Ley señala. Usted tiene derecho de acceder, rectificar y cancelar sus datos personales, así como de oponerse al tratamiento",
        "de los mismos o revocar el consentimiento que para tal fin nos haya otorgado, a través de los procedimientos que hemos implementado. Para conocer",
        "dichos procedimientos, los requisitos y plazos, se puede poner en contacto con personal de nuestra empresa en Calle 3 Picos 65, Polanco V Seccion,",
        "Miguel Hidalgo, Ciudad de México, México, CP 11560, tel: (52) 5521207273. Asimismo, le informamos que sus datos personales pueden ser transferidos",
        "y tratados dentro y fuera del país, por personas distintas a esta empresa. En ese sentido, su información puede ser compartida con empresas",
        "pertenecientes al Grupo Empresarial, para fines de calidad en el servicio y otros asuntos relacionados con la operación celebrada. Si usted no manifiesta",
        "su oposición para que sus datos personales sean transferidos, se entenderá que ha otorgado su consentimiento para ello.",
    ]
    for txt in aviso:
        c.drawString(ML, y, txt)
        y -= 9
    y -= 10

    # Tabla consentimiento
    bx, box_w = ML, (MR - ML) / 2
    by = y - 22
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.rect(bx, by, box_w, 22, fill=0, stroke=1)
    c.rect(bx + box_w, by, box_w, 22, fill=0, stroke=1)
    c.drawString(bx + 4, by + 13, "□  No consiento que mis datos personales sean transferidos en los")
    c.drawString(bx + 4, by + 4,  "términos que señala el presente aviso de privacidad.")
    c.drawString(bx + box_w + 4, by + 13, "□  Consiento que mis datos personales sean transferidos en los términos")
    c.drawString(bx + box_w + 4, by + 4,  "que señala el presente aviso de privacidad.")
    y = by - 12

    c.drawString(ML, y, "Si usted desea dejar de recibir mensajes promocionales de nuestra parte puede solicitarlo en la Calle 3 Picos 65, Polanco V Seccion, Miguel Hidalgo,")
    y -= 9
    c.drawString(ML, y, "Ciudad de México, México, CP 11560, tel: (52) 5521207273. Cualquier modificación a este aviso de privacidad podrá consultarla en")
    y -= 9
    c.setFillColor(colors.blue)
    c.drawString(ML, y, "https://getnea.com/terms.html")
    c.setFillColor(colors.black)
    c.drawString(ML + 115, y, " Fecha última actualización 01/03/2021")
    y -= 22

    sf(c, 8)
    c.drawString(ML, y, "Nombre y Firma del Cliente/Usuario")
    y -= 30

    line(c, ML, y, 310)
    sf(c, 9, bold=True)
    c.drawString(ML + 130, y + 6, "x")
    y -= 16

    sf(c, 8)
    c.drawString(ML, y, "Razón Social:")
    sf(c, 9, bold=True)
    c.drawString(ML + 64, y, D["firma_razon_social"])
    sf(c, 7.5)
    line(c, ML, y - 3, MR)
    y -= 20

    sf(c, 8)
    c.drawString(ML, y, "Representante Legal:")
    sf(c, 9, bold=True)
    c.drawString(ML + 96, y, D["firma_rep_legal"])
    sf(c, 7.5)
    line(c, ML, y - 3, MR)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def generar_pld(datos: dict, output_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=letter)
    page1(c, datos)
    c.showPage()
    page2(c, datos)
    c.showPage()
    c.save()
    print(f"PLD generado: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        datos = json.load(f)
    generar_pld(datos, sys.argv[2])
