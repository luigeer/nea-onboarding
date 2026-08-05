# -*- coding: utf-8 -*-
"""
generar_pld_pf.py — Formato PLD (Persona Física / PFAE) Nea Card
=================================================================
Anexo 3 del Acuerdo 02/2013. Genera el PDF desde cero con reportlab, con las
mismas convenciones visuales que generar_pld.py (Anexo 4, persona moral) para que
los dos formatos del expediente se vean iguales.

Diferencias frente al Anexo 4:
  - No hay razón social, constitución, poderes ni estructura accionaria
  - Se agrega el inciso ii) de constancia de CURP o cédula de identificación fiscal
  - Se agrega el inciso v) de actuación como apoderado de otra persona
  - La leyenda de desconocimiento del beneficiario controlador usa la variante de
    persona física: "actuó a cuenta propia y no a favor de terceros"

Uso:
    python generar_pld_pf.py <datos.json> <output.pdf>

Claves del diccionario: ver EJEMPLO al final del módulo.
"""

import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

W, H = letter
ML = 50
MR = 562
MT = 750

ROJO = colors.HexColor("#C0392B")

DOMICILIO_RESPONSABLE = ("Calle 3 Picos 65, Polanco V Seccion, Miguel Hidalgo, "
                         "Ciudad de México, México, CP 11560")
TEL_RESPONSABLE = "(52) 5521207273"

TIPOS_ID = [("ife", "IFE", 0), ("pasaporte", "PASAPORTE", 60),
            ("cedula", "CEDULA PROFESIONAL", 148), ("licencia", "LICENCIA", 253),
            ("migratorio", "DOCUMENTO MIGRATORIO", 308)]

COMPROBANTES = [("agua", "Agua", 0), ("luz", "Luz", 60), ("telefono", "Teléfono", 110)]

LEYENDA_PF = ("Declaro, bajo protesta de decir verdad, no tener conocimiento de la existencia de un "
              "Dueño Beneficiario/Beneficiario Controlador ya que actuó a cuenta propia y no a "
              "favor de terceros.")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — idénticos a generar_pld.py
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
        sf(c, restore_font_size)


def campo(c, y, etiqueta, valor, dx=None, hasta=MR, x=ML):
    """Etiqueta en regular, valor en negrita, subrayado hasta 'hasta'."""
    sf(c, 7.5)
    c.drawString(x, y, etiqueta)
    off = dx if dx is not None else c.stringWidth(etiqueta, "Helvetica", 7.5) + 4
    sf(c, 8, bold=True)
    c.drawString(x + off, y, str(valor) if valor is not None else "")
    sf(c, 7.5)
    line(c, x, y - 2, hasta)


def si_no(c, y, etiqueta, valor, x=ML):
    """Bloque 'etiqueta: SI [ ] NO [ ]' con la casilla correspondiente marcada."""
    sf(c, 7.5)
    c.drawString(x, y, etiqueta)
    base = x + c.stringWidth(etiqueta, "Helvetica", 7.5) + 8
    c.drawString(base, y, "SI")
    checkbox(c, base + 14, y, checked=bool(valor))
    c.drawString(base + 32, y, "NO")
    checkbox(c, base + 50, y, checked=not bool(valor))


def parrafo(c, y, lineas, size=7.5, dy=10, x=ML):
    sf(c, size)
    for t in lineas:
        c.drawString(x, y, t)
        y -= dy
    return y


def centrado(c, y, texto, size=7, bold=False, dy=9):
    """Bloque centrado que se ajusta al ancho útil sin desbordar los márgenes."""
    sf(c, size, bold=bold)
    font = "Helvetica-Bold" if bold else "Helvetica"
    for ln in wrap(c, texto, MR - ML, font=font, size=size):
        c.drawCentredString(W / 2, y, ln)
        y -= dy
    return y


def wrap(c, texto, ancho, font="Helvetica", size=7.5):
    palabras, out, act = texto.split(), [], ""
    for p in palabras:
        prueba = (act + " " + p).strip()
        if c.stringWidth(prueba, font, size) <= ancho:
            act = prueba
        else:
            if act:
                out.append(act)
            act = p
    if act:
        out.append(act)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA 1
# ─────────────────────────────────────────────────────────────────────────────
def page1(c, D):
    y = MT

    y = centrado(c, y,
                 "ANEXO 3 DEL ACUERDO 02/2013 POR EL QUE SE EMITEN LAS REGLAS DE CARÁCTER GENERAL "
                 "A QUE SE REFIERE LA LEY FEDERAL PARA LA PREVENCIÓN E IDENTIFICACIÓN DE "
                 "OPERACIONES CON RECURSOS DE PROCEDENCIA ILÍCITA", size=7, bold=True, dy=10)
    y -= 3
    y = centrado(c, y,
                 "DATOS Y DOCUMENTOS DE IDENTIFICACIÓN DE LOS CLIENTES DE QUIENES REALICEN "
                 "ACTIVIDADES VULNERABLES, RESPECTO DE AQUELLOS QUE SEAN PERSONAS FÍSICAS Y QUE "
                 "DECLAREN SER DE NACIONALIDAD MEXICANA O DE NACIONALIDAD EXTRANJERA CON LAS "
                 "CONDICIONES DE RESIDENTE TEMPORAL O RESIDENTE PERMANENTE, EN TÉRMINOS DE LA "
                 "LEY DE MIGRACIÓN.", size=7, dy=9)
    y -= 5
    y = centrado(c, y, "FORMULARIO DE IDENTIFICACIÓN DEL CLIENTE/USUARIO", size=8, bold=True, dy=10)
    y = centrado(c, y, "(PERSONAS FÍSICAS NACIONALES O EXTRANJERAS CON RESIDENCIA TEMPORAL / "
                       "PERMANENTE)", size=8, bold=True, dy=10)
    sf(c, 8)
    c.setFillColor(ROJO)
    c.drawCentredString(W / 2, y, "GRIT PAYMENT SOLUTIONS, S.A.P.I. DE C.V.")
    y -= 9
    c.drawCentredString(W / 2, y, DOMICILIO_RESPONSABLE)
    c.setFillColor(colors.black)
    y -= 16

    sf(c, 7.5)
    c.drawString(330, y, "Fecha de la operación (dd/mm/aa): %s" % D["fecha_operacion"])
    y -= 10
    c.drawString(262, y, "Actividad Vulnerable que se pretende realizar: Emisión de Tarjetas de "
                         "Servicio")
    y -= 16

    # ── I. INFORMACIÓN GENERAL ───────────────────────────────────────────────
    sf(c, 8, bold=True)
    c.drawString(ML, y, "I. INFORMACIÓN GENERAL")
    y -= 12
    sf(c, 7.5)
    c.drawString(ML, y, "NOMBRE COMPLETO [Apellido paterno, apellido materno y nombre(s), sin "
                        "abreviaturas]:")
    y -= 11
    sf(c, 8, bold=True)
    c.drawString(ML, y, D["nombre_completo"])
    sf(c, 7.5)
    line(c, ML, y - 2, MR)
    y -= 14

    campo(c, y, "Fecha de Nacimiento [día/mes/año]:", D["fecha_nacimiento"], hasta=290)
    campo(c, y, "País de Nacimiento:", D["pais_nacimiento"], hasta=MR, x=300)
    y -= 14
    campo(c, y, "País de Nacionalidad:", D["pais_nacionalidad"], hasta=200)
    campo(c, y, "CURP:", D["curp"], hasta=370, x=210)
    campo(c, y, "RFC:", D["rfc"], hasta=MR, x=380)
    y -= 14
    campo(c, y, "Actividad, ocupación, profesión o giro del negocio al que se dedica:",
          D["actividad_ocupacion"])
    y -= 18

    # ── II. DATOS DE CONTACTO ────────────────────────────────────────────────
    sf(c, 8, bold=True)
    c.drawString(ML, y, "II. DATOS DE CONTACTO")
    y -= 11
    sf(c, 7.5, bold=True)
    c.drawString(ML, y, "DOMICILIO PARTICULAR")
    y -= 13
    campo(c, y, "Calle:", D["calle"], hasta=400)
    campo(c, y, "No. Exterior/Interior:", D["num_ext"], hasta=MR, x=410)
    y -= 14
    campo(c, y, "Colonia:", D["colonia"], hasta=400)
    campo(c, y, "C.P.:", D["cp"], hasta=MR, x=410)
    y -= 14
    campo(c, y, "Del. o Mpio.:", D["municipio"], hasta=300)
    campo(c, y, "Estado:", D["estado"], hasta=MR, x=310)
    y -= 14
    campo(c, y, "País:", D["pais_domicilio"], hasta=300)
    y -= 14
    campo(c, y, "Teléfono [clave de larga distancia y, en su caso, extensión]:", D["telefono"],
          hasta=380)
    y -= 14
    campo(c, y, "Correo electrónico:", D["correo"], hasta=380)
    y -= 18

    # ── III. DATOS DE IDENTIFICACIÓN ─────────────────────────────────────────
    sf(c, 8, bold=True)
    c.drawString(ML, y, "III. DATOS DE IDENTIFICACIÓN")
    y -= 11
    sf(c, 7.5)
    c.drawString(ML, y, "PROPORCIONAR LOS SIGUIENTES DATOS DE ALGUNA IDENTIFICACIÓN OFICIAL:")
    y -= 13
    campo(c, y, "Tipo de identificación [nombre de la identificación como aparece en ella]:",
          D["tipo_id"])
    y -= 14
    campo(c, y, "Número de la identificación:", D["num_id"], hasta=380)
    y -= 14
    campo(c, y, "Autoridad emisora:", D["autoridad_emisora"], hasta=380)
    y -= 14
    campo(c, y, "País emisor:", D["pais_emisor"], hasta=300)
    y -= 24

    sf(c, 8, bold=True)
    c.drawString(ML, y, D["quien_lleno"])
    sf(c, 7.5)
    line(c, ML, y - 3, 330)
    y -= 12
    c.drawString(ML, y, "Nombre, firma y cargo de la persona que llenó el presente formulario")


# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA 2
# ─────────────────────────────────────────────────────────────────────────────
def page2(c, D):
    y = MT

    black_bar(c, y, "Documentos de identificación de personas físicas nacionales o extranjeras "
                    "con residencia temporal o permanente")
    y -= 20
    sf(c, 7.5)
    c.drawString(ML, y, "Incluir copia de la siguiente documentación:")
    y -= 16

    # i) identificación oficial
    sf(c, 7.5, bold=True)
    c.drawString(ML, y, "i)  Identificación oficial vigente (con fotografía)")
    y -= 14
    sf(c, 7.5)
    sel = D.get("tipo_id_oficial")
    for clave, etiqueta, dx in TIPOS_ID:
        c.drawString(ML + dx, y, etiqueta)
        ancho = c.stringWidth(etiqueta, "Helvetica", 7.5)
        checkbox(c, ML + dx + ancho + 4, y, checked=(sel == clave))
    y -= 20

    # ii) constancia de CURP o CIF
    sf(c, 7.5, bold=True)
    c.drawString(ML, y, "ii)  Constancia de la Clave Única de Registro de Población o Cédula de "
                        "Identificación Fiscal")
    y -= 10
    sf(c, 7.5)
    c.drawString(ML + 14, y, "expedida por el SAT, cuando el Cliente o Usuario cuente con ellas.")
    y -= 14
    si_no(c, y, "Se obtuvo constancia de CURP o cédula de identificación:",
          D.get("constancia_curp", True))
    y -= 20

    # iii) comprobante de domicilio
    sf(c, 7.5, bold=True)
    c.drawString(ML, y, "iii)  Comprobante de domicilio (vigencia no mayor a 3 meses)")
    y -= 14
    sf(c, 7.5)
    comp = D.get("comprobante_tipo")
    for clave, etiqueta, dx in COMPROBANTES:
        c.drawString(ML + dx, y, etiqueta)
        ancho = c.stringWidth(etiqueta, "Helvetica", 7.5)
        checkbox(c, ML + dx + ancho + 4, y, checked=(comp == clave))
    y -= 22

    # iv) constancia de beneficiario controlador
    black_bar(c, y, "Constancia de la existencia de algún beneficiario controlador")
    y -= 20
    sf(c, 7.5)
    c.drawString(ML, y, "iv)  Constancia por la que se acredite que quien realice la Actividad "
                        "Vulnerable solicitó a su Cliente o Usuario información acerca de si tiene")
    y -= 10
    c.drawString(ML + 14, y, "conocimiento de la existencia del Dueño Beneficiario, la cual deberá "
                             "estar firmada por los que participen directamente en el acto u "
                             "operación.")
    y -= 16
    si_no(c, y, "Se obtuvo comprobante conocimiento de existencia (cliente):",
          D.get("constancia_obtenida", True))
    y -= 20

    y = _bloque_declaracion(c, D, y)

    for txt in [
        "En el supuesto en que la persona física manifieste que sí tiene conocimiento de la "
        "existencia del Dueño Beneficiario, quien realice la Actividad",
        "Vulnerable deberá identificarlo de conformidad a lo dispuesto en la fracción VII del "
        "artículo 12 de las Reglas de Carácter General a que se refiere la",
        "Ley Federal para la Prevención e Identificación de Operaciones con Recursos de "
        "Procedencia Ilícita, cuando dicho Cliente o Usuario cuente con",
        "dicha información.",
    ]:
        c.drawString(ML, y, txt)
        y -= 10
    y -= 8

    # v) apoderado
    sf(c, 7.5, bold=True)
    c.drawString(ML, y, "v)  Carta poder o copia certificada del documento expedido por fedatario "
                        "público, cuando la persona física actúe como apoderado de otra")
    y -= 10
    sf(c, 7.5)
    c.drawString(ML + 14, y, "persona, así como copia de identificación oficial y comprobante de "
                             "domicilio del apoderado, con independencia de los datos y documentos")
    y -= 10
    c.drawString(ML + 14, y, "relativos al poderdante.")
    y -= 16
    apo = bool(D.get("actua_como_apoderado", False))
    si_no(c, y, "La persona física actúa como apoderado de otra persona:", apo)
    y -= 14
    if apo:
        si_no(c, y, "Se obtuvo carta poder o copia certificada de documento expedido por fedatario "
                    "público:", D.get("carta_poder_obtenida", False))
        y -= 14
    y -= 6

    # Aviso de privacidad
    black_bar(c, y, "AVISO DE PRIVACIDAD – PROTECCIÓN DE DATOS PERSONALES")
    y -= 18
    sf(c, 7)
    aviso = (
        "Grit Payment Solutions, S.A.P.I. de C.V., con domicilio en %s, es responsable de recabar "
        "sus datos personales, del uso que se le dé a los mismos y de su protección. Su información "
        "personal será utilizada para concretar la actividad que se señala al inicio del presente "
        "formato, así como para informarle sobre algún cambio o circunstancia que sea de su interés "
        "y evaluar la calidad del servicio que le brindamos. Lo anterior, en cumplimiento de lo "
        "dispuesto por la Ley Federal para la Prevención e Identificación de Operaciones con "
        "Recursos de Procedencia Ilícita, publicada en el Diario Oficial de la Federación el 17 de "
        "octubre de 2012. La información proporcionada en dicho formulario será empleada únicamente "
        "para efecto de cumplir con lo que dispone la citada Ley en cuanto a identificación de las "
        "personas con las que se realicen Actividades consideradas como Vulnerables, así como para "
        "la presentación de avisos ante la autoridad competente en los casos específicos que la "
        "propia Ley señala. Usted tiene derecho de acceder, rectificar y cancelar sus datos "
        "personales, así como de oponerse al tratamiento de los mismos o revocar el consentimiento "
        "que para tal fin nos haya otorgado, a través de los procedimientos que hemos implementado. "
        "Para conocer dichos procedimientos, los requisitos y plazos, se puede poner en contacto "
        "con personal de nuestra empresa en %s, tel: %s." % (
            DOMICILIO_RESPONSABLE, DOMICILIO_RESPONSABLE, TEL_RESPONSABLE))
    for ln in wrap(c, aviso, MR - ML, size=7):
        c.drawString(ML, y, ln)
        y -= 8.5
    y -= 8

    consiente = bool(D.get("consiente_transferencia", True))
    sf(c, 7)
    checkbox(c, ML, y, checked=consiente, size=8, restore_font_size=7)
    c.drawString(ML + 12, y, "Consiento que mis datos personales sean transferidos en los términos "
                             "que señala el presente aviso de privacidad.")
    y -= 12
    checkbox(c, ML, y, checked=not consiente, size=8, restore_font_size=7)
    c.drawString(ML + 12, y, "No consiento que mis datos personales sean transferidos en los "
                             "términos que señala el presente aviso de privacidad.")
    y -= 16

    sf(c, 6.5)
    c.drawString(ML, y, "Cualquier modificación a este aviso de privacidad podrá consultarla en "
                        "https://getnea.com/terms.html — Fecha última actualización 01/03/2021")
    y -= 26

    line(c, ML, y, 310)
    y -= 11
    sf(c, 8, bold=True)
    c.drawString(ML, y, D.get("firma_nombre", D["nombre_completo"]))
    y -= 11
    sf(c, 8)
    c.drawString(ML, y, "Nombre y Firma del Cliente/Usuario")


def _bloque_declaracion(c, D, y):
    """Declaración del cliente sobre el beneficiario controlador, variante persona física."""
    decl = D.get("bc_declaracion", "no_conoce")
    sf(c, 8, bold=True)
    c.drawString(ML, y, "Declaración del Cliente")
    y -= 12
    sf(c, 7.5)
    if decl == "no_conoce":
        texto = LEYENDA_PF
    else:
        n = D.get("bc_cantidad")
        detalle = ("de %s persona(s) física(s)" % n) if n else "de una o más personas físicas"
        texto = ("Declaro, bajo protesta de decir verdad, tener conocimiento de la existencia %s "
                 "con la calidad de Dueño Beneficiario/Beneficiario Controlador, cuyos datos de "
                 "identificación se asientan en el Formato de Identificación del Beneficiario "
                 "Controlador que forma parte de este expediente." % detalle)
    for ln in wrap(c, '"' + texto + '"', MR - ML):
        c.drawString(ML, y, ln)
        y -= 10
    y -= 12
    line(c, ML, y, ML + 260)
    y -= 10
    sf(c, 7)
    c.drawString(ML, y, "Nombre y firma del cliente, por su propio derecho")
    y -= 10
    sf(c, 8, bold=True)
    c.drawString(ML, y, D.get("firma_nombre", D["nombre_completo"]))
    y -= 16
    sf(c, 7.5)
    return y


# ─────────────────────────────────────────────────────────────────────────────
OBLIGATORIOS = ("fecha_operacion", "nombre_completo", "fecha_nacimiento", "pais_nacimiento",
                "pais_nacionalidad", "curp", "rfc", "actividad_ocupacion", "calle", "colonia",
                "cp", "municipio", "estado", "pais_domicilio", "telefono", "correo", "tipo_id",
                "num_id", "autoridad_emisora", "pais_emisor", "quien_lleno")


def _validar(D):
    faltantes = [k for k in OBLIGATORIOS if not D.get(k)]
    if faltantes:
        raise ValueError("Faltan campos obligatorios: %s" % ", ".join(faltantes))

    rfc = str(D["rfc"]).replace(" ", "").replace("-", "").upper()
    if len(rfc) != 13:
        raise ValueError("RFC con %d caracteres. Este formato es el Anexo 3, para persona física "
                         "(13 caracteres). Si es persona moral usa generar_pld.py." % len(rfc))
    D["rfc"] = rfc

    curp = str(D["curp"]).replace(" ", "").upper()
    if len(curp) != 18:
        raise ValueError("CURP inválida: se esperan 18 caracteres, se recibió %d." % len(curp))
    D["curp"] = curp

    if D.get("tipo_id_oficial") not in dict((k, v) for k, v, _ in TIPOS_ID):
        raise ValueError("tipo_id_oficial inválido: %r. Válidos: %s"
                         % (D.get("tipo_id_oficial"), [k for k, _, _ in TIPOS_ID]))
    if D.get("comprobante_tipo") not in dict((k, v) for k, v, _ in COMPROBANTES):
        raise ValueError("comprobante_tipo inválido: %r. Válidos: %s"
                         % (D.get("comprobante_tipo"), [k for k, _, _ in COMPROBANTES]))
    if D.get("actua_como_apoderado") and not D.get("carta_poder_obtenida"):
        raise ValueError("Si el cliente actúa como apoderado, el inciso v) exige carta poder o "
                         "copia certificada. Marca carta_poder_obtenida o corrige el supuesto.")
    if D.get("bc_declaracion", "no_conoce") == "conoce" and not D.get("bc_cantidad"):
        raise ValueError("Si el cliente declara conocer beneficiarios controladores, indica "
                         "bc_cantidad y genera el Formato de Identificación del Beneficiario "
                         "Controlador.")
    return D


def generar_pld_pf(datos: dict, output_path: str):
    """Genera el formato PLD Anexo 3 para persona física o PFAE."""
    D = _validar(dict(datos))
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=letter,
                      initialFontName="Helvetica", initialFontSize=7.5)
    c.setTitle("Formulario de Identificación del Cliente — Persona Física (Anexo 3)")
    page1(c, D)
    c.showPage()
    page2(c, D)
    c.showPage()
    c.save()
    print("PLD persona física generado: %s" % output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        generar_pld_pf(json.load(f), sys.argv[2])
