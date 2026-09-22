# -*- coding: utf-8 -*-
"""
generar_contrato_grit.py — Contrato de Prestación de Servicios de Grit Mobility
================================================================================
Contrato de prestación de servicios del monedero electrónico NEA CONTROL,
celebrado por Grit Mobility, S.A. de C.V. ("NEA" en el propio texto del
contrato — así se define en el preámbulo) y el cliente.

El cuerpo del contrato (declaraciones + 31 cláusulas) es texto legal FIJO,
igual para todos los clientes. Lo único dinámico ahí son dos datos de NEA que,
igual que en los demás generadores de Grit/Nea, son fijos y no se preguntan
por expediente:

    NEA_REPRESENTANTE      Luis Gómez Montijano
    NEA_ESCRITURA_PODERES  número 87,739, de fecha 16 de julio de 2025, ante
                           el Lic. Joaquín Ignacio Mendoza Pertierra, Notario
                           Público No. 62 de la Ciudad de México

Todo lo que varía por cliente vive en el Anexo A (Formato de Alta de
Clientes), que sí se genera desde datos.

Uso:
    python generar_contrato_grit.py <datos.json> <output.pdf>

Forma del diccionario de datos (ver DATOS_PM/DATOS_PFAE en
tests/test_generar_contrato_grit.py para un ejemplo completo):
    {
      "tipo_persona":      "moral" | "pfae",
      "razon_social":      str,
      "nombre_comercial":  str,
      "rfc_empresa":       str,
      "actividad_giro":    str,
      "nacionalidad":      str o None,      # solo PFAE
      "modelo_negocio":    "CLIENTE PREPAGO" | "CLIENTE POST-PAGO",
      "constitucion": {                     # None para PFAE
          "no_escritura", "fecha", "notario", "notaria_ubicacion",
          "folio_rpc", "fecha_inscripcion_rpc"
      },
      "representantes": [{"nombre", "escritura", "notario", "notaria"}, ...],  # 1-3
      "contacto": {"nombre", "telefono_1", "telefono_2", "correo"},
      "domicilio_fiscal": {"calle","num_ext","num_int","colonia","cp","municipio","estado"},
      "domicilio_entrega": {...} o None,    # None => se reutiliza el domicilio fiscal
      "comision", "cuota", "costo_tarjeta", "comentarios": str,
      "fecha_firma_larga": str,
    }
"""

import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, KeepTogether)

NEA_CORAL = colors.HexColor("#F1654B")
GRIS_BARRA = colors.HexColor("#EFEFEF")
GRIS_LINEA = colors.HexColor("#BFBFBF")
TEXTO = colors.HexColor("#1A1A1A")

MARGEN = 15 * mm
ANCHO_UTIL = letter[0] - 2 * MARGEN

# Fijos: no se preguntan por expediente (ver docstring del módulo).
NEA_REPRESENTANTE = "Luis Gómez Montijano"
NEA_ESCRITURA_PODERES = ("número 87,739, de fecha 16 de julio de 2025, otorgada ante la fe del "
                         "Licenciado Joaquín Ignacio Mendoza Pertierra, titular de la notaría "
                         "número 62 de la Ciudad de México")


# ─────────────────────────────────────────────────────────────────────────────
# Estilos
# ─────────────────────────────────────────────────────────────────────────────
def _estilos():
    base = dict(fontName="Helvetica", fontSize=8, leading=10.5, textColor=TEXTO)
    return {
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=10,
                                 leading=13, alignment=TA_CENTER, textColor=TEXTO),
        "seccion": ParagraphStyle("seccion", fontName="Helvetica-Bold", fontSize=9,
                                  leading=12, alignment=TA_CENTER, textColor=TEXTO),
        "clausula": ParagraphStyle("clausula", fontName="Helvetica-Bold", fontSize=8.3,
                                   leading=11, textColor=NEA_CORAL,
                                   spaceBefore=6, spaceAfter=3),
        "cuerpo": ParagraphStyle("cuerpo", **base),
        "justo": ParagraphStyle("justo", alignment=TA_JUSTIFY, **base),
        "seccion_barra": ParagraphStyle("seccion_barra", fontName="Helvetica-Bold", fontSize=8.2,
                                        leading=10, textColor=TEXTO),
        "firma": ParagraphStyle("firma", fontName="Helvetica-Bold", fontSize=8,
                                leading=10, alignment=TA_CENTER, textColor=TEXTO),
        "firma_sub": ParagraphStyle("firma_sub", fontName="Helvetica", fontSize=7,
                                    leading=9, alignment=TA_CENTER,
                                    textColor=colors.HexColor("#555555")),
    }


def _barra(texto, S):
    t = Table([[Paragraph(texto, S["seccion_barra"])]], colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_BARRA),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, NEA_CORAL),
    ]))
    return t


def _campos(pares, S, cols=2):
    """Rejilla de etiqueta/valor, dos columnas. Un valor vacío se muestra como '—'."""
    filas, buffer = [], []
    for etiqueta, valor in pares:
        celda = Paragraph("<b>%s:</b> %s" % (etiqueta, valor if valor not in (None, "") else "—"),
                          S["cuerpo"])
        buffer.append(celda)
        if len(buffer) == cols:
            filas.append(buffer)
            buffer = []
    if buffer:
        filas.append(buffer + [""] * (cols - len(buffer)))
    t = Table(filas, colWidths=[ANCHO_UTIL / cols] * cols)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
    ]))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Cuerpo fijo: declaraciones y las 31 cláusulas
# ─────────────────────────────────────────────────────────────────────────────
def _clausulado():
    """Lista de flowables del cuerpo fijo del contrato.

    Cada entrada de CONTENIDO es (titulo_o_None, texto). 'texto' puede traer
    varios párrafos separados por '\\n\\n'. Cuando titulo no es None se dibuja
    como encabezado de cláusula/declaración antes del texto.
    """
    CONTENIDO = [
        (None,
         "CONTRATO DE PRESTACIÓN DE SERVICIOS QUE CELEBRAN POR UNA PARTE GRIT MOBILITY, S.A. "
         "DE C.V., REPRESENTADO EN ESTE ACTO POR %s (A QUIEN EN LO SUCESIVO SE LE DENOMINARÁ "
         "COMO “NEA”), Y POR OTRA PARTE EL CLIENTE IDENTIFICADO EN EL ANEXO A, FORMATO DE ALTA "
         "DE CLIENTES (A QUIEN EN LO SUCESIVO SE LE DENOMINARÁ COMO \"EL CLIENTE”), Y EN SU "
         "CONJUNTO DENOMINADOS COMO “LAS PARTES”, AL TENOR DE LAS SIGUIENTES DECLARACIONES Y "
         "CLÁUSULAS:" % NEA_REPRESENTANTE),

        ("__seccion__", "D E C L A R A C I O N E S"),

        ("I. Declara NEA, por conducto de su representante legal, bajo protesta de decir "
         "verdad, que:",
         "a) Es una sociedad mercantil legalmente constituida conforme a las leyes de los "
         "Estados Unidos Mexicanos bajo escritura pública número 9,996 de fecha 19 de "
         "diciembre de 2019, otorgada ante la fe del Licenciado Jorge Luis Ramos Uriarte, "
         "Notario Público número 4 de Ocotlán, Jalisco, cuyo primer testimonio se encuentra "
         "debidamente inscrita en el Registro Público de Comercio de Jalisco, bajo Folio "
         "Mercantil Electrónico número N-2020004940 de fecha 24 de enero de 2020.\n\n"
         "b) Su representante cuenta con las facultades y poderes suficientes para celebrar "
         "el presente contrato y obligarlo en los términos del mismo, las cuales le fueron "
         "otorgadas mediante la escritura pública %s, las cuales no le han sido modificadas, "
         "revocadas o limitadas, a las que no ha renunciado a la fecha de celebración del "
         "presente contrato.\n\n"
         "c) Dentro de su objeto social se encuentra contemplada la emisión de monederos "
         "electrónicos destinados para la adquisición de combustibles para vehículos "
         "marítimos, aéreos y terrestres en estaciones de servicio de expendio al público de "
         "petrolíferos dentro del territorio nacional. Se encuentra debidamente inscrita ante "
         "el Registro Federal de Contribuyentes bajo la clave: TFM191231NA7. Su domicilio "
         "fiscal se encuentra localizado en Calle 3 Picos 65, Polanco V Secc, Miguel Hidalgo, "
         "CP 11560, CDMX.\n\n"
         "d) Cuenta con todos los permisos, licencias y autorizaciones necesarios para llevar "
         "a cabo los servicios objeto del Contrato, así como para obligarse en términos del "
         "mismo." % NEA_ESCRITURA_PODERES),

        ("II. Declara el “CLIENTE”, por conducto de su representante legal, bajo protesta de "
         "decir verdad, que:",
         "a) Es una sociedad inscrita ante el Registro Público de la mexicana, debidamente "
         "constituida de conformidad con las leyes de los Estados Unidos Mexicanos, cuyos "
         "datos de constitución, incluyendo número de escritura pública, fecha, notario, "
         "número de notaría, ubicación, folio mercantil y fecha de inscripción, se especifican "
         "en el Anexo A, Formato de Alta de Clientes, que forma parte integral del presente "
         "Contrato.\n\n"
         "b) Su representante cuenta con las facultades y poderes suficientes para celebrar "
         "el presente contrato y obligarlo en los términos del mismo, los datos de la "
         "escritura de poderes, incluyendo número, fecha, notario, notaría y folio de "
         "inscripción, se especifican en el Anexo A, Formato de Alta de Clientes. Dichas "
         "facultades no le han sido modificadas, revocadas o limitadas y a las que no ha "
         "renunciado a la fecha de celebración del presente contrato por lo que subsisten en "
         "todos y cada uno de sus términos y fuerza legal.\n\n"
         "c) Se encuentra debidamente inscrita ante el Registro Federal de Contribuyentes "
         "(RFC) bajo la clave especificada en el Anexo A, Formato de Alta de Clientes.\n\n"
         "d) Su domicilio fiscal se encuentra especificado en el Anexo A, Formato de Alta de "
         "Clientes.\n\n"
         "e) Es su deseo celebrar el presente Contrato con NEA a efecto de que éste le "
         "proporcione monederos electrónicos para el personal que EL CLIENTE designe, los "
         "cuales serán destinados exclusivamente para la adquisición de combustibles para "
         "vehículos marítimos, aéreos y terrestres en las Estaciones de Servicio Afiliadas en "
         "la República Mexicana.\n\n"
         "f) Es propietario de los recursos con los cuales va a cumplir con las obligaciones "
         "originadas por el presente Contrato, actuando en todo momento a nombre y por cuenta "
         "propia, y manifestando que dichos recursos provendrán en su totalidad de fuentes de "
         "riqueza consideradas como lícitas por las leyes de los Estados Unidos Mexicanos al "
         "igual que por la legislación internacional aplicable y/o por los criterios "
         "generalmente aceptados para efecto de prevenir y combatir el lavado de dinero y el "
         "financiamiento al terrorismo, independientemente del país o territorio donde dichos "
         "ingresos hayan sido generados.\n\n"
         "g) Toda la documentación e información necesaria para una clara identificación "
         "según datos señalados en entrega a NEA y adjunta al presente instrumento."),

        ("III. Declaran las PARTES, por conducto de su representante legal, que:",
         "A) Celebran el presente Contrato sin que el error, el dolo, la mala fe, la violencia "
         "o cualquier otro vicio afecte su consentimiento.\n\n"
         "B) Conocen las disposiciones legales y fiscales a las que cada una se someten en "
         "virtud del Contrato.\n\n"
         "C) Con base en las anteriores declaraciones, las PARTES están de acuerdo en "
         "celebrar el presente contrato al tenor de las siguientes:"),

        ("__seccion__", "C L Á U S U L A S"),

        ("PRIMERA. - DEFINICIONES",
         "Las Partes acuerdan en que los términos que se utilicen en el presente Contrato y "
         "que se describen a continuación, tendrán el significado que se les atribuye en las "
         "siguientes definiciones, en el entendido de que dichas definiciones aplicarán para "
         "el género masculino o femenino, e independientemente de que los mismos se usen en "
         "singular o plural, o si las mismas se escriben con mayúsculas o minúsculas:\n\n"
         "Acuerdo Operativo: es el conjunto de términos y condiciones específicos que regulan "
         "la operación del servicio entre las Partes, el cual se integra por las cláusulas de "
         "Vigencia y Condiciones Generales de Uso, Saldo y Depósitos, Periodo de Facturación, "
         "Contraprestaciones y Condiciones de Pago, Estaciones de Servicio Afiliadas, "
         "Autenticación, entre otras clausulas contenidas en el presente Contrato.\n\n"
         "Afiliados: Estaciones de Servicios que han suscrito un contrato de afiliación con "
         "NEA, a efecto de aceptar los monederos electrónicos NEA CONTROL como medios de pago "
         "para la adquisición de Combustibles.\n\n"
         "Call-Center: Se refiere al centro de atención al cliente que NEA pondrá a "
         "disposición del cliente a efecto de que este pueda reportar incidencias en la "
         "operación del portal, las tarjetas, estaciones de servicio afiliadas o solicitar "
         "informacion de cualquier tema relacionado con el monedero electrónico Nea Control.\n\n"
         "Combustibles: se refiere a las gasolinas regular y premium, así como al diésel "
         "automotriz, de conformidad con la definición de dichos términos en la legislación "
         "vigente.\n\n"
         "Contrato: el presente Contrato de prestación de servicios, sus Anexos y los términos "
         "y condiciones aplicables al Sistema, al Portal y a los monederos NEA CONTROL.\n\n"
         "Dispersión: se refiere al depósito de fondos monetarios con cargo al Saldo de El "
         "CLIENTE que NEA hará en los monederos NEA CONTROL por instrucciones de EL CLIENTE a "
         "efecto de que sus USUARIOS puedan adquirir Combustibles en las Estaciones de "
         "Servicio Afiliadas.\n\n"
         "Estaciones de Servicio: Instalación para el almacenamiento, abastecimiento y "
         "expendio de gasolinas y/o diésel, como dicho término se define en la legislación "
         "vigente.\n\n"
         "Monederos electrónicos: de conformidad con la legislación fiscal, se entiende por "
         "monedero electrónico a cualquier dispositivo tecnológico o medio de pago que se "
         "encuentre asociado a un sistema de pagos utilizado por EL CLIENTE y/o los USUARIOS "
         "que éste designe para la adquisición de combustibles para vehículos marítimos, "
         "aéreos y terrestres en las Estaciones de Servicio Afiliadas. Asimismo, para efectos "
         "del contrato, las menciones a los monederos electrónicos se referirán a los "
         "monederos NEA CONTROL.\n\n"
         "NEA CONTROL: el instrumento de almacentamiento de valor monetario con claves de "
         "autenticación que NEA pone a disposición de EL CLIENTE y de los USUARIOS que éste "
         "determine, a efecto de que estos últimos los utilicen como monederos electrónicos "
         "para la adquisición de combustibles para vehículos marítimos, aéreos y terrestres en "
         "las Estaciones de Servicio Afiliadas.\n\n"
         "Partes: NEA y EL CLIENTE.\n\n"
         "Periodo de Facturación: será el periodo de tiempo acordado por las Partes para "
         "calcular las transacciones realizadas por EL CLIENTE y sus USUARIOS, para hacer un "
         "corte de las mismas y para proceder a su facturación.\n\n"
         "Portal: se refiere al portal electrónico que NEA pondrá a disposición de EL CLIENTE "
         "a efecto de que éste pueda administrar las tarjetas NEA CONTROL que le proporcione "
         "NEA, así como revisar saldos, gestionar emisión de facturas, reportar incidencias, "
         "entre otros. Mismo que a la firma de contrato se enviará por correo electrónico "
         "pasos a seguir como acceso al mismo.\n\n"
         "Saldo: Fondos que EL CLIENTE haya depositado a NEA de forma previa a la utilización "
         "de los monederos NEA CONTROL, a efecto de que EL CLIENTE y sus USUARIOS puedan "
         "adquirir Combustibles en las Estaciones de Servicio Afiliadas.\n\n"
         "Sistema: es la plataforma tecnológica, herramientas informáticas e instrumentos "
         "físicos necesarios para utilizar los monederos electrónicos NEA CONTROL. El sistema "
         "proporciona, entre otros, los servicios de liquidación y compensación de pagos que "
         "se realicen entre EL CLIENTE y/o sus USUARIOS, NEA y las Estaciones de Servicio "
         "Afiliadas.\n\n"
         "Territorio Nacional: se refiere a la República Mexicana.\n\n"
         "Transacción: se refiere a los depósitos de recursos realizados por EL CLIENTE y a "
         "cualquier uso de los monederos electrónicos NEA CONTROL, por parte de los USUARIOS "
         "para la adquisición de Combustibles en las Estaciones de Servicio Afiliadas.\n\n"
         "USUARIO: son las personas físicas designadas por EL CLIENTE para utilizar los "
         "monederos electrónicos NEA CONTROL para la adquisición de Combustibles en las "
         "Estaciones de Servicio Afiliadas."),

        ("SEGUNDA. - OBJETO",
         "A través del presente Contrato, NEA proporcionará a EL CLIENTE los monederos "
         "electrónicos NEA CONTROL que éste le indique a efecto de que los USUARIOS puedan "
         "adquirir Combustibles para vehículos marítimos, aéreos y terrestres en las "
         "Estaciones de Servicio Afiliadas que se encuentren en Territorio Nacional.\n\n"
         "Los monederos electrónicos NEA CONTROL únicamente podrán destinarse para la "
         "adquisición de Combustibles en las Estaciones de Servicio Afiliadas y no podrán, "
         "por ninguna circunstancia, utilizarse para disponer de efectivo, intercambiarse por "
         "títulos de crédito, ni para adquirir bienes o servicios distintos a los "
         "Combustibles. Asimismo, bajo los términos del presente instrumento, EL CLIENTE se "
         "obliga a que, bajo ningún supuesto, ni el propio cliente ni sus USUARIOS solicitaran "
         "a las Estaciones de Servicio la expedición de un Comprobante Fiscal Digital por "
         "Internet CFDI respecto de los consumos de combustible que adquieran a través del "
         "monedero electrónico NEA CONTROL.\n\n"
         "A través del Sistema y de los monederos electrónicos, NEA se obliga a pagar a las "
         "Estaciones de Servicio Afiliadas los consumos de Combustibles que realicen los "
         "USUARIOS designados por EL CLIENTE, a cargo del Saldo que éste tenga depositado en "
         "la cuenta específica que NEA le asigne.\n\n"
         "EL CLIENTE reconoce y acepta que NEA podrá negarse, sin responsabilidad alguna de su "
         "parte, a hacer la dispersión de fondos a las Estaciones de Servicio Afiliadas por el "
         "uso de los monederos electrónicos NEA CONTROL si EL CLIENTE no cuenta con Saldo "
         "suficiente para cubrir los montos erogados por los USUARIOS.\n\n"
         "NEA se reserva el derecho de denegar, suspender o restringir las operaciones de EL "
         "CLIENTE o sus USUARIOS, sin responsabilidad alguna, cuando existan indicios o "
         "sospechas de actividades relacionadas con la prevención de lavado de dinero y "
         "financiamiento al terrorismo, requerimientos de autoridades competentes, procesos "
         "regulatorios, incumplimiento de la normatividad aplicable, o cualquier otra causa "
         "que a juicio de NEA ponga en riesgo la integridad del Sistema o el cumplimiento de "
         "sus obligaciones legales."),

        ("TERCERA. – VIGENCIA",
         "El presente Contrato tendrá una vigencia de 1 (un) año, el cual iniciará a partir "
         "de la fecha de su firma del presente.\n\n"
         "Asimismo, las Partes aceptan que el contrato podrá ser prorrogable por periodos "
         "iguales de 1 (un) año, salvo acuerdo en contrario entre las Partes, lo cual deberá "
         "quedar por escrito.\n\n"
         "Si alguna de las partes deseara dar por terminado el contrato, deberá informar a la "
         "otra mediante escrito previo y con 60 días naturales de anticipación, dando solo así "
         "por terminado el contrato, sin responsabilidad alguna y sin necesidad de previa "
         "declaración judicial, subsistiendo la obligación de pago de las cantidades adeudadas "
         "por EL CLIENTE a la fecha de terminación.\n\n"
         "Para el caso de una terminación anticipada en la modalidad de postpago, en la que EL "
         "CLIENTE sea quién solicite dicha terminación a NEA, no surtirá efectos dicha "
         "terminación hasta que EL CLIENTE liquide el importe total de los Productos "
         "consumidos además de reintegrar a satisfacción de NEA los productos no dispuestos.\n\n"
         "Una vez recibida la solicitud de cancelación EL CLIENTE podrá seguir operando los "
         "monederos de combustible hasta la fecha de terminación de contrato, a partir de esa "
         "fecha serán inhabilitados. Queda bajo responsabilidad de EL CLIENTE destruir "
         "debidamente los plásticos con el fin de evitar fraudes o mal uso de los mismos. El "
         "CLIENTE será el único responsable del mal uso que le puedan dar posterior a "
         "cancelada la cuenta y desde este momento El CLIENTE libera a NEA de cualquier "
         "responsabilidad al respecto.\n\n"
         "Así mismo, una vez concluido el contrato o efectuada la recisión de éste, EL CLIENTE "
         "dejará de tener acceso al Sistema a los 30 (treinta) días naturales contados a "
         "partir de la fecha de terminación efectiva, sin responsabilidad alguna para NEA. "
         "Durante este plazo EL CLIENTE únicamente podrá consultar en el Portal sus facturas y "
         "estados de cuenta."),

        ("CUARTA. - SALDO Y DEPÓSITOS",
         "Una vez celebrado el presente Contrato, EL CLIENTE podrá modificar el número de "
         "monederos electrónicos requeridos, los USUARIOS asignados, los montos autorizados "
         "por USUARIO y monedero, así como la periodicidad en la que estarán disponibles los "
         "recursos para cada USUARIO y monedero, a través del Portal puesto a disposición de "
         "EL CLIENTE por NEA. EL CLIENTE está obligado a identificar el monto requerido para "
         "todos sus consumos, así mismo deberá informar a NEA el monto total de Fondos "
         "solicitados a través de una Solicitud de Fondos.\n\n"
         "Con base en las necesidades de EL CLIENTE y conforme a lo acordado en el presente "
         "documento, EL CLIENTE deberá realizar los depósitos de recursos suficientes para "
         "cubrir, en la periodicidad acordada, los montos que los USUARIOS asignados tendrán "
         "disponibles en sus monederos electrónicos NEA CONTROL.\n\n"
         "a) Si el banco en el que se realiza el depósito de recursos es el mismo banco "
         "utilizado por NEA, la dispersión a los monederos electrónicos de los USUARIOS se "
         "realizará en un plazo de 24 (veinticuatro) horas hábiles.\n\n"
         "b) Si el banco en el que se realiza el depósito de recursos es distinto al banco "
         "utilizado por NEA, la dispersión a los monederos electrónicos de los USUARIOS se "
         "realizará en un plazo de 48 (cuarenta y ocho) horas hábiles.\n\n"
         "EL CLIENTE libera de responsabilidad a NEA en caso de que aquél no realice el "
         "depósito de recursos a su Saldo y que por dicha razón los USUARIOS se encuentren "
         "imposibilitados a realizar la adquisición de Combustibles en las Estaciones de "
         "Servicio Afiliadas."),

        ("QUINTA. - PERIODO DE FACTURACIÓN",
         "NEA pondrá a disposición de EL CLIENTE a través del Portal, un estado de cuenta con "
         "las transacciones realizadas por EL CLIENTE y sus USUARIOS en cada Periodo de "
         "Facturación. Dicho Estado de Cuenta contendrá los depósitos realizados por EL "
         "CLIENTE, el Saldo al final del Periodo de Facturación y las transacciones "
         "realizadas por los USUARIOS con los monederos NEA CONTROL.\n\n"
         "Al final de cada Periodo de Facturación, NEA realizará un corte de transacciones y "
         "emitirá a favor de EL CLIENTE, en un plazo no mayor a 7 (siete) días hábiles a "
         "partir del fin del Periodo, un comprobante fiscal digital por internet (CFDI) y su "
         "complemento de estado de cuenta de combustibles, mismos que cumplirán con todos los "
         "requisitos legales y fiscales ordenados por las leyes vigentes y las autoridades "
         "competentes. El complemento de estado de cuenta de combustibles contendrá los "
         "consumos de Combustible efectivamente realizados por los USUARIOS en el Periodo en "
         "cuestión, mismos que serán previamente conciliados con las Estaciones de Servicio "
         "Afiliadas.\n\n"
         "En el referido corte de transacciones, se facturará el importe total de la "
         "Contraprestación a que tenga derecho NEA por la prestación de los Servicios objeto "
         "del presente Contrato, el importe de los gastos administrativos relacionados con la "
         "emisión y administración de los monederos electrónicos y demás herramientas "
         "tecnológicas provistas por NEA, así como cualquier otro cargo por contraprestación "
         "del que NEA sea acreedor.\n\n"
         "Las transacciones por adquisición de Combustibles que no hubieran sido efectivamente "
         "realizadas en el Periodo de Facturación y que, por lo tanto, no se encontraran "
         "conciliadas con las Estaciones de Servicio Afiliadas, no formarán parte del "
         "complemento de estado de cuenta correspondiente a dicho Periodo, sino que serán "
         "parte del complemento de estado de cuenta de combustibles del periodo en el que "
         "finalmente sean conciliadas.\n\n"
         "EL CLIENTE deberá pagar a NEA todas las transacciones que por adquisición de "
         "Combustibles realicen sus USUARIOS, independientemente del Periodo de Facturación "
         "en el que se llevaron a cabo, y el pago respectivo deberá efectuarlo máximo dentro "
         "de los 7 (siete) días hábiles siguientes a la recepción del CFDI, en términos de lo "
         "señalado en la Cláusula SEXTA.\n\n"
         "Cualquier otro concepto o cargo distinto a los aquí referidos se facturará por "
         "separado."),

        ("SEXTA. - CONTRAPRESTACIONES Y CONDICIONES DE PAGO",
         "Los montos de las Contraprestaciones por los Servicios de NEA que se muestran en el "
         "Anexo A podrán ser ajustados a partir del primer año de vigencia del presente "
         "Contrato.\n\n"
         "EL CLIENTE y NEA acuerdan el oportuno y debido cumplimiento de todas y cada una de "
         "las obligaciones a cargo de EL CLIENTE que se deriven del presente contrato, a "
         "efecto de tener Saldo suficiente y disponible en la cuenta concentradora, y de esta "
         "forma poder asignar saldo para que los USUARIOS utilicen los monederos electrónicos "
         "para la adquisición de Combustibles en las Estaciones de Servicio Afiliada. EL "
         "CLIENTE se obliga a depositar las cantidades necesarias y suficientes en la cuenta "
         "bancaria que NEA le indique."),

        ("SÉPTIMA. - ESTACIONES DE SERVICIO AFILIADAS",
         "El listado con las Estaciones de Servicio Afiliadas será publicado en el sitio "
         "https://nea-control.com y podrá ser consultado por EL CLIENTE y los USUARIOS. NEA "
         "se reserva el derecho a modificar de tiempo en tiempo el listado de Estaciones de "
         "Servicio Afiliadas, por lo que es responsabilidad de EL CLIENTE y de los USUARIOS "
         "verificar constantemente el Portal a efecto de conocer cualquier actualización de "
         "los establecimientos Afiliados.\n\n"
         "EL CLIENTE y sus USUARIOS deberán rechazar que las Estaciones de Servicio Afiliadas "
         "realicen el cobro de cualquier sobreprecio, comisión o cualquier otro concepto "
         "distinto al precio de los Combustibles adquiridos, y deberán reportar esta "
         "situación inmediatamente a NEA.\n\n"
         "NEA no será responsable en ningún momento de la calidad o cantidad de Combustibles "
         "adquiridos por los USUARIOS en las Estaciones de Servicio Afiliadas, así como por "
         "cualquier daño o perjuicio ocasionado a EL CLIENTE o a los USUARIOS a causa de la "
         "adquisición de Combustible en dichas Estaciones, toda vez que NEA únicamente es "
         "responsable por la prestación del servicio de sistema de pagos y por la emisión y "
         "administración de monederos electrónicos utilizados para la adquisición de "
         "Combustibles en los establecimientos Afiliados.\n\n"
         "NEA se compromete a proveer a las Estaciones de Servicio Afiliadas, bajo su mejor "
         "esfuerzo y conforme a la disponibilidad tecnológica, la infraestructura necesaria "
         "para procesar los pagos realizados con los monederos electrónicos NEA CONTROL. "
         "Dicha infraestructura podrá incluir, de manera enunciativa mas no limitativa: "
         "terminales punto de venta (TPV), lectores de código QR, lectores de tarjetas con "
         "chip, dispositivos de comunicación de campo cercano (NFC), lectores de matrículas "
         "vehiculares, tags de radiofrecuencia (RFID), lectores biométricos, así como "
         "cualquier otra tecnología que NEA implemente para la autenticación y procesamiento "
         "de Transacciones. La selección, instalación y mantenimiento de dicha infraestructura "
         "será determinada por NEA de acuerdo con las características operativas de cada "
         "Estación de Servicio Afiliada y las necesidades del Sistema."),

        ("OCTAVA. - AUTENTICACIÓN",
         "EL CLIENTE podrá determinar a través del Portal los niveles de autenticación que "
         "los USUARIOS deberán acreditar ante las Estaciones de Servicio Afiliadas para poder "
         "utilizar los monederos electrónicos NEA CONTROL.\n\n"
         "Dichos niveles de autenticación se determinarán con base en cualquier combinación "
         "de los siguientes parámetros: 1) Número de Identificación Personal (NIP) que consta "
         "de 4 números los cuales pueden ser elegidos por el USUARIO; 2) Número de placas de "
         "tránsito del vehículo vinculado al USUARIO (solo se incluyen los números existentes "
         "en las placas); 3) Número de identificación del USUARIO asignado por EL CLIENTE "
         "conocido en el sistema como ID de conductor; 4) (Odómetro) Kilometraje del vehículo "
         "vinculado al USUARIO.\n\n"
         "Asimismo, EL CLIENTE podrá determinar como criterios de autorización de uso de los "
         "monederos NEA CONTROL por parte de los USUARIOS, los siguientes: a) Horario; b) "
         "Zonas geográficas; c) Días de uso; d) Capacidad de depósito del vehículo; e) Volumen "
         "máximo por transacción.\n\n"
         "EL CLIENTE únicamente podrá hacer modificaciones en el Sistema a los niveles de "
         "autenticación o criterios de uso de los monederos NEA CONTROL asignados a los "
         "USUARIOS."),

        ("NOVENA. - MONEDEROS ELECTRÓNICOS",
         "NEA entregará en el domicilio indicado por EL CLIENTE los monederos electrónicos "
         "NEA CONTROL que éste solicite a NEA, en un plazo máximo de 10 (diez) días hábiles a "
         "partir de la solicitud que EL CLIENTE realice. Tanto la solicitud como el pago "
         "deberán efectuarse a través de los medios establecidos por NEA. EL CLIENTE asume la "
         "responsabilidad de confirmar recepción de los monederos electrónicos. Previo al "
         "envío de la primera solicitud de saldos, usando el procedimiento descrito en el "
         "Manual de Usuario Administrador mismo que se estará otorgando a EL CLIENTE.\n\n"
         "NEA se reserva el derecho, como propietario de los monederos NEA CONTROL, a "
         "sustituirlos, bloquearlos o modificar las condiciones de su funcionamiento, cuando "
         "lo considere necesario a efecto de garantizar la calidad de los Servicios, previa "
         "notificación por escrito al CLIENTE. Por seguridad los monederos electrónicos que "
         "no registren transacciones en un plazo de 60 días naturales se cancelarán "
         "automáticamente y los fondos o recursos que tuvieren disponibles serán devueltos al "
         "saldo de EL CLIENTE.\n\n"
         "EL CLIENTE acepta que en caso de pérdida por robo o extravío de cualquier monedero "
         "electrónico NEA CONTROL es responsabilidad tanto de EL CLIENTE como del USUARIO "
         "reportar la tarjeta NEA CONTROL a la brevedad posible el administrador de la "
         "flotilla deberá solicitar este procedimiento a través del Call-Center para su "
         "bloqueo y de esta manera evitar el mal uso de la misma. En caso de transacciones no "
         "reconocidas EL USUARIO debe de levantar una aclaración misma que se evaluará para "
         "poder brindar una respuesta, en el entendido que NEA no está obligado a la "
         "devolución de recursos a EL CLIENTE por un mal uso de la tarjeta. Las acciones que "
         "NEA tomará se encontrarán basadas en el dictamen de la aclaración.\n\n"
         "EL CLIENTE en este acto acepta que la no utilización de los monederos NEA, así como "
         "su bloqueo provisional o definitivo, no lo liberará de la responsabilidad de pagar "
         "a NEA cualquier cargo que por Contraprestación se hubiere generado a favor de NEA."),

        ("DÉCIMA. - SISTEMA Y PORTAL",
         "EL CLIENTE deberá utilizar el Portal en Línea en los términos del Manual del Portal "
         "en Línea que se entregará al momento de la firma de contrato. NEA otorgará a EL "
         "CLIENTE acceso al Portal console.ationet.com a efecto de que pueda administrar y "
         "dar de alta a nuevos USUARIOS, acceda a sus estados de cuenta, pueda verificar el "
         "monto de las transacciones realizadas por los USUARIOS con los monederos NEA "
         "CONTROL, solicitud de nuevas tarjetas, Reglas de carga en cada tarjeta, entre otros "
         "servicios que ofrece el sistema/portal en línea.\n\n"
         "EL CLIENTE dispondrá de un acceso asegurado y encriptado al Portal. NEA "
         "proporcionará las claves de acceso y contraseña provisional a EL CLIENTE a través de "
         "los correos electrónicos indicados en la Cláusula de DOMICILIOS Y COMUNICACIONES de "
         "este Contrato. EL CLIENTE deberá acceder por primera vez al Portal utilizando "
         "dichas claves y procederá a cambiar la contraseña, la cual será exclusivamente del "
         "conocimiento de EL CLIENTE.\n\n"
         "Cualquier uso del Portal y del Sistema por parte de EL CLIENTE supondrá la "
         "aceptación sin reservas de los términos y condiciones que los regulan, los cuales "
         "serán dados a conocer por NEA al momento de proporcionarle a EL CLIENTE las claves "
         "de acceso iniciales.\n\n"
         "NEA también pondrá a disposición de EL CLIENTE y de los USUARIOS herramientas para "
         "la consulta de saldos de los monederos NEA CONTROL asignados a través del Portal.\n\n"
         "NEA no será responsable del uso indebido o irresponsable de las claves de acceso y "
         "contraseñas de EL CLIENTE para acceder al Portal o utilizar el Sistema, así como "
         "tampoco de los usos que los empleados, representantes, administradores o USUARIOS "
         "designados por EL CLIENTE hagan de dichas herramientas informáticas. EL CLIENTE será "
         "el único responsable de conservar, resguardar y utilizar correctamente las claves "
         "de acceso y contraseñas, así como de compartirlas únicamente con el personal que "
         "autorice y designe para utilizar el Portal o el Sistema."),

        ("DÉCIMA PRIMERA. - CALL-CENTER",
         "NEA pondrá a disposición de EL CLIENTE y sus USUARIOS, un centro de atención "
         "telefónica destinado a Servicio al Cliente, en el que EL CLIENTE y sus USUARIOS "
         "podrán: realizar reportes sobre la calidad de los Servicios; solicitar asesoría "
         "sobre el uso del Sistema, del Portal y/o de los monederos NEA CONTROL; levantar "
         "reportes relacionados con los Servicios, así como por fallas en el Sistema y en el "
         "Portal, o por el robo, pérdida, destrucción o deterioro de los monederos "
         "electrónicos NEA CONTROL; solicitar aclaraciones respecto a las transacciones "
         "realizadas por los USUARIOS; verificar la lista de Estaciones de Servicio "
         "Afiliadas; solicitar el bloqueo o cancelación, a entera responsabilidad de EL "
         "CLIENTE y/o de los USUARIOS, de cualquier monedero electrónico NEA CONTROL; "
         "solicitar información sobre transacciones realizadas; cualquier otro servicio o "
         "prestación que NEA determine de tiempo en tiempo, los cuales serán comunicados al "
         "CLIENTE a través del Portal o del correo electrónico que EL CLIENTE dé de alta en "
         "el Sistema."),

        ("DÉCIMA SEGUNDA. - OBLIGACIONES",
         "Adicionalmente a las obligaciones señaladas específicamente en otras cláusulas del "
         "contrato EL CLIENTE y usuarios tiene las siguientes: A) Consultar de manera "
         "constante el Portal a efecto de conocer actualizaciones en los términos y "
         "condiciones de uso del Sistema y de los monederos NEA CONTROL, así como cualquier "
         "promoción que NEA ponga a su disposición o los servicios adicionales que EL CLIENTE "
         "podría contratar. B) A utilizar de la manera convenida en este Contrato, y en los "
         "manuales de uso que NEA ponga a disposición de EL CLIENTE y los USUARIOS, el Portal, "
         "el Sistema y los monederos electrónicos NEA CONTROL como proporcionar los recursos "
         "suficientes para los USUARIOS, de manera que éstos puedan utilizarlos para la "
         "adquisición de Combustibles. C) A pagar por las Contraprestaciones a las que NEA "
         "tuviera derecho en virtud del presente Contrato. D) A comunicar a los USUARIOS que "
         "el uso de los monederos electrónicos NEA CONTROL será bajo su exclusiva "
         "responsabilidad y que deberán ser utilizados únicamente para la adquisición de "
         "Combustibles en las Estaciones de Servicio Afiliadas como los términos y "
         "condiciones que rigen el uso de los monederos electrónicos NEA CONTROL. E) A "
         "reportar de manera inmediata a NEA, cualquier falla en el Sistema. F) A no "
         "modificar, alterar, ceder, vender o reproducir de forma alguna los monederos "
         "electrónicos NEA CONTROL, haciéndose responsable EL CLIENTE ante NEA de las "
         "acciones que en este sentido realicen sus USUARIOS. G) A responder ante NEA de "
         "cualquier uso indebido que los USUARIOS hagan del Sistema, el Portal y/o los "
         "monederos electrónicos NEA CONTROL y, en su caso, pagar a NEA los gastos y costos "
         "en que éste incurriera para remediar o solucionar los problemas resultantes del uso "
         "indebido de las herramientas aquí mencionadas. H) A cumplir y a hacer cumplir a sus "
         "USUARIOS cualquier otra obligación que les corresponda en términos del presente "
         "Contrato, de sus Anexos, de los términos y condiciones de uso del Sistema, del "
         "Portal y de los monederos electrónicos NEA CONTROL y de las disposiciones legales "
         "vigentes, incluyendo aquellas de carácter fiscal.\n\n"
         "II) OBLIGACIONES DE NEA\n\n"
         "A) Reportar oportunamente a EL CLIENTE las ventanas de mantenimiento al Sistema y al "
         "Portal que pudieran afectar su operación, así como el correcto funcionamiento de los "
         "monederos electrónicos NEA CONTROL. Salvo que el mantenimiento respectivo se deba a "
         "una emergencia, caso fortuito o fuerza mayor, NEA notificará a EL CLIENTE con por lo "
         "menos 24 (veinticuatro) horas de anticipación la duración de las ventanas de "
         "mantenimiento, así como la reactivación del Sistema, del Portal y/o de los "
         "monederos NEA CONTROL. B) A emitir los CFDIs y los complementos de estado de cuenta "
         "de combustibles de conformidad con lo ordenado en la legislación fiscal vigente. C) "
         "A mantener actualizado el sitio web con Estaciones de Servicio Afiliadas. D) A "
         "atender las aclaraciones, reclamaciones y/o quejas que realicen EL CLIENTE y sus "
         "USUARIOS de conformidad con lo establecido en este Contrato. E) A mantener operativo "
         "y en funcionamiento el Call-Center, en los horarios de funcionamiento y con los "
         "niveles de servicio acordados por las Partes, salvo por caso de emergencia, caso "
         "fortuito o fuerza mayor."),

        ("DÉCIMA TERCERA. - ACLARACIONES Y RECLAMACIONES",
         "Cualquier aclaración o reclamación que EL CLIENTE y/o cualquiera de los USUARIOS "
         "tuvieren respecto a la operatividad del Sistema, del Portal o de los monederos "
         "electrónicos, así como aquellas relativas a transacciones no reconocidas, deberán "
         "ser comunicadas a NEA a través del Portal o del Call-Center en un plazo máximo de "
         "15 (quince) días naturales contados a partir de la fecha del evento que fuere motivo "
         "de la aclaración o reclamación, debiendo EL CLIENTE y/o los USUARIOS proporcionar a "
         "NEA toda la información y documentación que éste les requiriera para fundamentar la "
         "aclaración o reclamación.\n\n"
         "Si EL CLIENTE y/o los USUARIOS no cumplen con los plazos y requisitos establecidos "
         "anteriormente, la aclaración o reclamación será rechazada por NEA, sin "
         "responsabilidad alguna para NEA.\n\n"
         "Si EL CLIENTE y/o los USUARIOS cumplen con los plazos y requisitos indicados por "
         "NEA, NEA admitirá la aclaración o reclamación para su revisión y contará con un "
         "plazo máximo de 60 (sesenta) días naturales para responder y resolver sobre éstas.\n\n"
         "No obstante lo anterior, EL CLIENTE se obliga a pagar el total de las facturas CFDIs "
         "o adeudos que tuvieren con NEA, incluso aquellos que sean objeto de la aclaración o "
         "reclamación, hasta en tanto NEA resuelva lo conducente. Si la aclaración o "
         "reclamación es procedente y de ella se deriva el derecho de EL CLIENTE y/o los "
         "USUARIOS a alguna devolución de recursos, NEA hará el reembolso respectivo o emitirá "
         "una nota de crédito por el monto correspondiente, en un plazo que no excederá de 20 "
         "(veinte) días hábiles a partir de la resolución de la aclaración o reclamación que "
         "fuere procedente.\n\n"
         "NEA no será responsable por fallas en el funcionamiento de los monederos "
         "electrónicos NEA CONTROL y del Sistema, si éstos no son utilizados por EL CLIENTE y "
         "sus USUARIOS de la manera convenida con NEA, conforme a los términos y condiciones "
         "establecidos en este Contrato y en los manuales que de dichas herramientas NEA "
         "ponga a su disposición."),

        ("DÉCIMA CUARTA. – PÉRDIDA POR ROBO O EXTRAVÍO, DETRIORO O DESTRUCCIÓN DE MONEDEROS "
         "ELECTRÓNICOS",
         "Es responsabilidad de EL CLIENTE levantar un acta sobre la pérdida por robo o "
         "extravío de los monederos electrónicos NEA CONTROL a NEA a través del Call-Center, "
         "así como deshabilitar el monedero desde el portal de usuario, para evitar un mal "
         "uso del mismo. En caso de deterioro o destrucción de los monederos electrónicos, EL "
         "CLIENTE deberá notificar a NEA a través del Call-Center y solicitar la reposición de "
         "los mismos, cubriendo los costos de reposición indicados en el ANEXO A.\n\n"
         "En virtud de lo anterior, NEA no será responsable de las transacciones o consumos de "
         "Combustible que se pudieran efectuar con el monedero NEA CONTROL en caso de que EL "
         "CLIENTE y los USUARIOS omitan realizar la notificación y/o acciones necesarias con "
         "el reporte por pérdida por robo o extravío de manera inmediata a partir de dichos "
         "eventos. En cualquiera de los supuestos establecidos en esta Cláusula, EL CLIENTE "
         "deberá pagar a NEA la reposición o sustitución de los monederos electrónicos NEA "
         "CONTROL, así como cualquier Contraprestación a la que NEA tuviera derecho por la "
         "prestación de los Servicios.\n\n"
         "EL CLIENTE deberá coadyuvar a NEA, en todo momento y a su entera cuenta y cargo, en "
         "las investigaciones que NEA y/o la autoridad competente ordenen para resolver "
         "cualquier controversia relacionada con el robo, pérdida, deterioro o destrucción de "
         "los monederos electrónicos NEA CONTROL."),

        ("DÉCIMA QUINTA. - CONTINGENCIAS",
         "En caso de alguna falla en la terminal, de alguna Estación de Servicio no será "
         "posible realizar transacción alguna por cuestiones de seguridad, misma falla debe "
         "ser reportada al Centro de Atención a Clientes."),

        ("DÉCIMA SEXTA. - IMPUESTOS Y DEDUCCIONES",
         "Cada una de las Partes será responsable de retener, trasladar o pagar a la "
         "autoridad tributaria los impuestos y contribuciones de los que sea causante.\n\n"
         "Será responsabilidad exclusiva de EL CLIENTE la determinación de los impuestos a su "
         "cargo y de las deducciones a las que tuviera derecho por la utilización de los "
         "monederos NEA CONTROL, así como por la contratación de los Servicios objeto del "
         "presente Contrato. Por lo tanto, NEA no será responsable en caso de que las "
         "autoridades tributarias hagan reclamación alguna en su contra por el incorrecto "
         "cálculo y determinación de los impuestos y deducciones que EL CLIENTE tuviera que "
         "hacer.\n\n"
         "Asimismo, será exclusiva responsabilidad de EL CLIENTE el correcto acreditamiento "
         "del Impuesto al Valor Agregado (IVA) que se genere por los Servicios contratados a "
         "NEA y la adquisición de los monederos NEA CONTROL.\n\n"
         "EL CLIENTE y sus USUARIOS se obligan a no solicitar CFDI a las Estaciones de "
         "Servicio Afiliadas por las transacciones realizadas con los monederos NEA CONTROL, "
         "de conformidad con lo establecido por la Ley del Impuesto Sobre la Renta y la "
         "Resolución Miscelánea Fiscal vigente."),

        ("DÉCIMA SÉPTIMA. - TERMINACIÓN Y RESCISIÓN",
         "A) TERMINACIÓN ANTICIPADA\n\n"
         "Las Partes podrán dar por terminado anticipadamente el presente Contrato con aviso "
         "por escrito con acuse de recibo dado a la otra Parte, con por lo menos 60 (sesenta) "
         "días naturales de anticipación a la fecha efectiva de terminación. No obstante lo "
         "anterior, las Partes reconocen que deberán cumplir con todas obligaciones que "
         "estuvieren a su cargo hasta la fecha de terminación efectiva e incluso con aquéllas "
         "que deban de cumplirse con posterioridad si las mismas se hubieran generado "
         "previamente a la fecha de terminación.\n\n"
         "En caso de que EL CLIENTE notifique a NEA una fecha de terminación efectiva en un "
         "plazo menor al acordado en el párrafo anterior, EL CLIENTE deberá pagar a NEA una "
         "pena convencional equivalente a 6 (seis) meses de Contraprestación, calculados con "
         "base en las Contraprestaciones a que NEA tuviera derecho al momento de la "
         "notificación de terminación realizada por EL CLIENTE.\n\n"
         "Dicha pena convencional deberá pagarse dentro de los 5 (cinco) días hábiles "
         "siguientes a aquél en que NEA se lo solicite al CLIENTE.\n\n"
         "EL CLIENTE se obliga a liquidar cualquier adeudo que tuviere con NEA, de lo "
         "contrario, la terminación anticipada solicitada por aquél no surtirá efectos sino "
         "hasta que EL CLIENTE haya cubierto todos los adeudos que tuviere a su cargo.\n\n"
         "Si EL CLIENTE cumplió con los plazos y formalidades establecidos al inicio de este "
         "inciso, NEA deberá reembolsarle a través de transferencia bancaria cualquier Saldo "
         "a favor que tuviere EL CLIENTE dentro de 30 (treinta) días naturales siguientes a la "
         "fecha efectiva de terminación del Contrato.\n\n"
         "Una vez realizada la notificación de terminación anticipada, EL CLIENTE no podrá "
         "dar de alta a nuevos USUARIOS ni podrá modificar las condiciones de uso de los "
         "monederos electrónicos que éstos tuvieren asignados.\n\n"
         "B) RESCISIÓN\n\n"
         "En caso de incumplimiento a cualquiera de las obligaciones a cargo de EL CLIENTE, "
         "NEA estará facultado para suspender la prestación de los Servicios o a rescindir el "
         "presente Contrato.\n\n"
         "Si EL CLIENTE es omiso en realizar el pago de las Contraprestaciones debidas a NEA, "
         "éste estará facultado para suspender la prestación de los Servicios de manera "
         "inmediata, sin responsabilidad alguna para NEA. Si dicho incumplimiento se prolonga "
         "por más de 15 (quince) días naturales, NEA estará facultado para rescindir el "
         "presente Contrato, bastando para ello notificación por escrito a la cuenta de "
         "correo electrónico dada de alta en el Sistema por EL CLIENTE.\n\n"
         "La rescisión del Contrato no implicará de ninguna manera que EL CLIENTE pueda dejar "
         "de pagar los Servicios que NEA hubiere prestado durante la vigencia del Contrato.\n\n"
         "Una vez comunicada la rescisión del Contrato, NEA inhabilitará los monederos "
         "electrónicos que se le hayan otorgado a EL CLIENTE así como el acceso al Portal.\n\n"
         "Adicionalmente, en caso de rescisión del Contrato por causas imputables a EL "
         "CLIENTE, NEA tendrá derecho a recibir por concepto de pena convencional una "
         "cantidad equivalente a 6 (seis) meses de Contraprestación, calculados con base en "
         "las Contraprestaciones a que NEA tuviera derecho al momento de la notificación de "
         "rescisión realizada por NEA.\n\n"
         "Dicha pena convencional deberá pagarse dentro de los 5 (cinco) días hábiles "
         "siguientes a aquél en que NEA se lo solicite al CLIENTE.\n\n"
         "Si al momento de la rescisión EL CLIENTE tuviere Saldo disponible en su cuenta, EL "
         "CLIENTE acepta que NEA podrá utilizar dicho monto para compensar el monto de las "
         "Contraprestaciones debidas y/o el monto de la pena convencional por rescisión, "
         "debiendo EL CLIENTE pagar a NEA la diferencia restante en los términos del párrafo "
         "anterior."),

        ("DÉCIMA OCTAVA. - CASO FORTUITO Y FUERZA MAYOR",
         "Ninguna de las Partes será responsable frente a la otra por incumplimiento o falta "
         "de cumplimiento oportuno, total o parcial, al presente Contrato, ocasionado por "
         "causas o circunstancias que no puedan ser controladas por cualquiera de ellas o por "
         "las Estaciones de Servicio Afiliadas, incluyendo de manera enunciativa y no "
         "limitativa caso fortuito, fuerza mayor, órdenes o restricciones gubernamentales, "
         "guerra o condiciones semejantes a ésta, amenaza de terrorismo, terrorismo, "
         "epidemia, pandemia, declaratorias de emergencia emitidas por las autoridades, "
         "movilizaciones, bloqueos comerciales internacionales; huelgas, paros o conflictos "
         "sindicales no imputables a las Partes; averías, disminución, falla o corte en los "
         "servicios de suministro de energía eléctrica, de telecomunicaciones, de sistemas de "
         "datos o redes de internet, siempre y cuando fueran imprevisibles, o en caso de ser "
         "previsibles, fueran inevitables; restricciones de importación o exportación "
         "impuestas por la autoridad correspondiente; embargos no imputables a las Partes; o "
         "cualquier otro acto de naturaleza y efecto similar.\n\n"
         "También será considerado como caso fortuito o fuerza mayor, el terrorismo o "
         "incidentes cibernéticos, es decir, actos maliciosos de cómputo como hacking, "
         "malware, ataque de denegación de servicios y acceso no autorizado, los daños "
         "derivados de la violación a la seguridad cibernética, y la manipulación de "
         "información generada, enviada, recibida, almacenada o comunicada por medios "
         "electrónicos, ópticos o similares, siempre y cuando éstos supuestos no deriven de "
         "negligencia, culpa o dolo de cualquiera de las Partes.\n\n"
         "La falta de recursos financieros o el cambio de condiciones comerciales en el "
         "mercado no serán considerados como una causa o circunstancia que no pueda ser "
         "controlada por una de las Partes.\n\n"
         "Adicionalmente, para los efectos del presente Contrato, “Fuerza Mayor” significa un "
         "acontecimiento imprevisible o inevitable, general, absoluto, fuera del control de "
         "una de las Partes, que sea la causa del incumplimiento, sea que provenga de "
         "acontecimientos de la naturaleza o de hechos del hombre incluyendo, sin limitación, "
         "actos de autoridad competente, siempre y cuando éstos últimos no hayan sido "
         "provocados por la Parte que invoca el Caso Fortuito o Fuerza Mayor.\n\n"
         "En cualquier supuesto anterior, por el que se impida o retrase el cumplimiento del "
         "presente Contrato, la Parte que invoque el supuesto de Caso Fortuito o Fuerza Mayor "
         "deberá comunicar esta situación a la otra Parte, por correo electrónico, vía "
         "telefónica o cualquier otro medio en el que conste fehacientemente esta "
         "notificación en un plazo máximo de 5 (cinco) días naturales a partir del surgimiento "
         "del evento de Caso Fortuito o Fuerza Mayor. En caso de que no se cumpla con esta "
         "formalidad, la Parte que invoque el Caso Fortuito o Fuerza Mayor no quedará eximida "
         "del cumplimiento de sus obligaciones, salvo acuerdo por escrito en contrario "
         "suscrito por las Partes.\n\n"
         "Siempre y cuando las Partes hayan cumplido con las formalidades aquí exigidas, "
         "tendrán la posibilidad de acordar una suspensión en el cumplimiento de las "
         "obligaciones mientras dure el evento de Caso Fortuito o Fuerza Mayor. Si dicho "
         "evento se prolonga más de 1 (un) meses contados a partir de la fecha de notificación "
         "del Caso Fortuito o Fuerza Mayor, las Partes tendrán derecho a terminar el presente "
         "Contrato, sin responsabilidad alguna para ellas, quedando subsistentes sólo aquellas "
         "obligaciones que se hubieren originado y cumplido previo a la declaración del Caso "
         "Fortuito o Fuerza Mayor.\n\n"
         "Los eventos de Caso Fortuito o Fuerza Mayor que afecten a cualquiera de las "
         "Estaciones de Servicio Afiliadas aprovecharán como si fueran propios a NEA respecto "
         "al cumplimiento de las obligaciones de este Contrato."),

        ("DÉCIMA NOVENA. - CESIÓN",
         "EL CLIENTE acepta que no podrá, bajo ningún concepto, ceder, enajenar o transmitir, "
         "total o parcialmente, los derechos y obligaciones que le corresponden en virtud del "
         "presente Contrato, salvo autorización expresa y por escrito de NEA. En caso de "
         "contravención, NEA estará facultado a rescindir el presente Contrato y a exigir de "
         "EL CLIENTE la pena convencional establecida en la Cláusula Décima Séptima.\n\n"
         "NEA no podrá, bajo ningún concepto, gravar, ceder, enajenar o transmitir, total o "
         "parcialmente, los derechos y obligaciones que le corresponden en virtud del presente "
         "Contrato, ni los derechos derivados de su autorización como emisor de monederos "
         "electrónicos utilizados en la adquisición de combustibles para vehículos marítimos, "
         "aéreos y terrestres, otorgada por el Servicio de Administración Tributaria, en "
         "términos de lo dispuesto por la regla 3.3.1.12. de la Resolución Miscelánea Fiscal "
         "vigente."),

        ("VIGÉSIMA. - DATOS PERSONALES",
         "NEA se obliga a cumplir de manera rigurosa con la Ley de Protección de Datos "
         "Personales en Posesión de los Particulares y la normatividad relacionada con la "
         "misma, en el tratamiento de los datos personales y patrimoniales de EL CLIENTE y/o "
         "de sus USUARIOS. EL CLIENTE tendrá todos los derechos que le otorgan las leyes en "
         "la materia para solicitar el acceso, rectificación, cancelación u oposición al "
         "tratamiento de sus datos personales y patrimoniales y los de sus USUARIOS."),

        ("VIGÉSIMA PRIMERA. - PROPIEDAD INTELECTUAL",
         "Ninguna de las disposiciones de este Contrato se entenderá de manera alguna como "
         "algún derecho otorgado por NEA al CLIENTE y/o a sus USUARIOS, para utilizar "
         "cualquier marca, diseño, logo, nombre comercial, signo distintivo, patente, derecho "
         "de autor o cualquier otro derecho de propiedad intelectual, de los cuales NEA sea "
         "titular, salvo convenio expreso por escrito celebrado entre las Partes. El "
         "incumplimiento a lo anterior será causal de rescisión del Contrato en términos de "
         "la Cláusula Décima Séptima."),

        ("VIGÉSIMA SEGUNDA. - NATURALEZA DEL CONTRATO",
         "Las Partes reconocen y aceptan que el presente Contrato es de naturaleza mercantil "
         "y se regirá conforme a la legislación civil, mercantil y fiscal aplicable en la "
         "República Mexicana.\n\n"
         "Asimismo, las Partes manifiestan que la celebración del presente Contrato no "
         "implica la constitución de asociación o sociedad alguna entre ellas, incluyendo "
         "asociación en participación, ni implica cualquier tipo de subordinación que pudiera "
         "estar regulada por ordenamientos distintos a los indicados anteriormente.\n\n"
         "Cada una de las Partes se reconoce como el único patrón de los trabajadores que "
         "tiene a su cargo, por lo que cada una será responsable de las obligaciones "
         "obrero-patronales y cargas sociales de las que cada una deba hacerse cargo respecto "
         "al personal que tengan contratado o subcontratado.\n\n"
         "El hecho de que EL CLIENTE otorgue a los USUARIOS el uso de los monederos "
         "electrónicos de NEA como una prestación por el trabajo personal subordinado que "
         "realicen para aquél, no implicará de ninguna manera que NEA es el obligado o "
         "responsable de otorgar dicha prestación a los empleados de EL CLIENTE.\n\n"
         "EL CLIENTE, a su entera cuenta y cargo, se obliga a sacar en paz y a salvo a NEA de "
         "cualquier reclamación de carácter laboral o de seguridad social que los "
         "trabajadores y/o USUARIOS de aquél interpusieran contra NEA. Asimismo, EL CLIENTE "
         "deberá reembolsar inmediatamente a NEA cualquier gasto en que éste haya incurrido "
         "para procurar su defensa de las reclamaciones aquí referidas, incluyendo aquellos "
         "gastos relacionados con honorarios de abogados. EL CLIENTE también será responsable "
         "de reembolsar a NEA de manera inmediata cualquier monto que hubiera erogado por "
         "concepto de multas o sanciones impuestas por la autoridad, por causas imputables a "
         "EL CLIENTE."),

        ("VIGÉSIMA TERCERA. - CONFIDENCIALIDAD",
         "En virtud de la celebración del presente Contrato y de la prestación de Servicios "
         "que llevará a cabo NEA en favor de EL CLIENTE, las Partes manifiestan que han "
         "compartido y que compartirán entre sí información sensible que deberá ser tratada "
         "en todo momento como Información Confidencial. La Información Confidencial aquí "
         "referida incluirá, de manera enunciativa mas no limitativa, lo siguiente: datos "
         "personales, procesos de negocio, planes estratégicos, planes de marketing, "
         "especificaciones técnicas, claves, contraseñas, NIPS, diseños, dibujos, materiales "
         "impresos, promocionales, sistemas informáticos, condiciones comerciales, entre "
         "otros, así como cualquier otra información que se comunique de manera verbal, "
         "escrita o transmitida por cualquier medio físico, electrónico, óptico o auditivo, "
         "que las Partes se compartan como parte de los derechos y obligaciones a los que se "
         "sujetan por este Contrato.\n\n"
         "La Información Confidencial compartida por el titular de la misma (en lo sucesivo, "
         "el “Emisor”) a la otra parte (en lo sucesivo, el “Receptor”), será en todo momento "
         "propiedad del Emisor. El Receptor no tendrá derecho alguno sobre la Información "
         "Confidencial y tampoco estará facultada para utilizarla o divulgarla salvo para "
         "cumplir con el objeto del presente Contrato. En ese sentido, la divulgación de la "
         "Información Confidencial no implicará de modo alguno concesión a favor del Receptor "
         "para su reproducción ni se considerará como el otorgamiento de una licencia de uso "
         "de derechos de propiedad intelectual propiedad del Emisor.\n\n"
         "Las obligaciones aquí previstas no serán aplicables en los siguientes casos: si la "
         "Información Confidencial fuera de dominio público previa o posteriormente a la "
         "celebración de este Contrato o si aquélla obrara en poder del Receptor y no esté "
         "sujeta a las obligaciones aquí establecidas y no hubiere sido divulgada por parte "
         "del Emisor, o si se trata de información que debe de divulgarse en virtud de la "
         "legislación vigente o por mandamiento ordenado por autoridad competente; si la "
         "Información Confidencial es obtenida por el Receptor de manera legal por la "
         "transmisión que de ella haga una tercera persona que no se encontrare obligada a "
         "mantener el secreto respecto a esta información; o si la Información Confidencial "
         "fuere conocida por el Receptor antes de su divulgación por parte del Emisor, "
         "siempre que el Receptor acredite dicho conocimiento.\n\n"
         "El Receptor reconoce que será responsable de demostrar cualquier excepción que le "
         "asistiera respecto a la acción que el Emisor interpusiera contra aquél por la "
         "divulgación de la Información Confidencial.\n\n"
         "Si el presente Contrato se diera por terminado o concluyera por cualquier motivo, "
         "el Receptor estará obligado a devolver al Emisor toda la Información Confidencial "
         "que conservara en su poder, ya sea en medios físicos o electrónicos o a través de "
         "cualquier formato en el que se encontrara contenida la Información Confidencial. "
         "Asimismo, si el Emisor lo requiriera, el Receptor deberá destruir la Información "
         "Confidencial que le ordenare el Emisor y proporcionar prueba de dicha destrucción "
         "al Emisor.\n\n"
         "Además de las obligaciones anteriormente mencionadas, el Receptor de la Información "
         "Confidencial deberá: mantener la Información Confidencial en estricto resguardo y "
         "no revelarla a ninguna otra parte o tercera persona, relacionada o no con el "
         "Contrato, salvo con el consentimiento previo y por escrito del Emisor; instruir al "
         "personal que estará encargado de recibir y tratar la Información Confidencial de su "
         "obligación de recibir, tratar y usar dicha información de acuerdo con las "
         "obligaciones de confidencialidad aquí pactadas, así como a utilizar la Información "
         "únicamente para cumplir con el objeto del presente Contrato — el personal "
         "anteriormente mencionado deberá suscribir a su vez los acuerdos de confidencialidad "
         "que aseguren el correcto tratamiento de la Información Confidencial del Emisor; y "
         "divulgar la Información Confidencial únicamente a las personas autorizadas para su "
         "recepción dentro de su organización y a aquéllas que fuere necesario para el "
         "estricto cumplimiento de este Contrato.\n\n"
         "El incumplimiento de cualquiera de las Partes a las obligaciones de confidencialidad "
         "aquí contenidas, le facultará a exigir de la otra la rescisión del Contrato, así "
         "como la indemnización por daños y perjuicios que su incumplimiento le hubieren "
         "causado."),

        ("VIGÉSIMA CUARTA. – PRIVACIDAD DE DATOS",
         "Conforme con lo dispuesto en la legislación vigente en materia de protección de "
         "datos personales en posesión de particulares, NEA pone a disposición de EL CLIENTE "
         "su Aviso de Privacidad a través de la siguiente dirección electrónica: "
         "https://nea-control.com/aviso-de-privacidad\n\n"
         "Asimismo, EL CLIENTE expresamente manifiesta y otorga a NEA su consentimiento para "
         "que sus datos puedan compartirse a terceros con los que NEA tenga relaciones "
         "contractuales para fines de calidad en el servicio.\n\n"
         "Las partes en relación con las transferencias Datos Personales en general "
         "(entiéndase cualquier información concerniente a una persona física identificada o "
         "identificable) y Datos Personales sensibles (entiéndase aquellos datos personales "
         "que afecten a la esfera más íntima de su titular, o cuya utilización indebida pueda "
         "dar origen a discriminación o conlleve un riesgo grave para éste), definir de manera "
         "precisa y documentada cuando NEA CONTROL podrá transferir datos de EL CLIENTE sin "
         "responsabilidad alguna a cargo de NEA.\n\n"
         "EL CLIENTE acepta y reconoce que NEA podrá compartir sus datos personales generales "
         "y sensibles con sus empresas afiliadas o subsidiarias, con terceros proveedores de "
         "servicios para el cumplimiento de las obligaciones legales adquiridas por NEA, "
         "socios comerciales con los que NEA lleve a cabo convenios o contratos enfocados al "
         "desarrollo de nuevos productos y/o servicios para satisfacer diversas necesidades "
         "del cliente o el ofrecimiento de productos y/o servicios complementarios a los que "
         "ofrece NEA, así como también de manera enunciativa más no limitativa cualquier "
         "prestador de servicio cuya actividad y/o finalidad sea la de recuperación de "
         "cartera vencida y adeudos en general, todas las cuales deberán proteger la "
         "información recibida, la cual se regirá por el aviso de privacidad que NEA tenga "
         "publicado y por el aviso de privacidad de la empresa receptora siempre con apego a "
         "la Ley.\n\n"
         "Ambas partes convienen que realizarán todo lo humanamente posible para dar "
         "cumplimiento a lo señalado por el artículo 73 del Reglamento de la Ley Federal de "
         "Protección de Datos Personales en Posesión de Particulares y demás aplicable, "
         "regulando su relación como Responsables Transferentes y Responsables Receptores "
         "respectivamente, y cuando así corresponda de acuerdo con los términos acordados.\n\n"
         "En virtud de lo anterior EL CLIENTE acepta que NEA comunique a terceros Datos "
         "Personales generales y sensibles sobre los cuales estos últimos tomará decisiones "
         "de Tratamiento y Medidas de Seguridad, tales como: A) Identificación de Bases de "
         "Datos — NEA determinará individualmente los datos personales generales y/o "
         "sensibles que entregará al Responsable Receptor, así como la forma de entregar "
         "dicha información, estableciendo por escrito los detalles de la transferencia y de "
         "los datos personales a transferir; en cualquier caso NEA como el Responsable "
         "Transferente buscará que el Responsable Receptor garantice que cuenta con el "
         "equipo, medidas de seguridad, infraestructura y personal para recibir las bases de "
         "datos, así como para mantener la confidencialidad, integridad y disponibilidad de "
         "la información comunicada por el Responsable Transferente. B) Licitud de las "
         "transferencias — EL CLIENTE sabe y acepta que, desde la celebración y firma del "
         "presente contrato se hace sabedor que NEA podrá transmitir sus datos personales "
         "generales y/o sensibles, considerando este como su formal consentimiento, sin "
         "responsabilidad alguna a cargo de NEA. C) Medidas de Seguridad — se establece que "
         "el Responsable Receptor deberá implementar medidas de seguridad administrativas, "
         "técnicas y físicas que permitan proteger los datos personales contra daño, "
         "pérdida, alteración, destrucción o el uso, acceso o tratamiento no autorizado, y "
         "cualesquiera otras que le fueren impuestas o en cumplimento con la Ley Federal de "
         "Protección de Datos Personales en Posesión de Particulares o para garantizar la "
         "correcta protección de los Datos Personales en cada caso, habida cuenta del estado "
         "de la tecnología, la naturaleza de los datos almacenados y los riesgos a los que "
         "estén expuestos. D) Derechos de los Titulares — cada Parte será responsable de "
         "atender las solicitudes de los Titulares sobre el ejercicio de los Derechos ARCO "
         "previstos por la LFPD y su Reglamento; en particular NEA deberá atender las "
         "solicitudes sobre el ejercicio de los Derechos ARCO efectuadas en relación con la "
         "información contenida en la base de datos consolidada de la cual será responsable. "
         "E) Contenido y Comunicación de Avisos de Privacidad — la firma del presente "
         "contrato constituye prueba del conocimiento de EL CLIENTE en el sentido de que el "
         "Responsable Receptor tiene sobre la existencia y contenido del Aviso de Privacidad "
         "Integral que regula el Tratamiento de los Datos Personales que NEA le transfiere; "
         "tal Aviso de Privacidad deberá ser respetado conforme a lo señalado en este "
         "instrumento, las disposiciones de la Ley Federal de Protección de Datos Personales "
         "en Posesión de Particulares, su Reglamento y cualquier otra disposición que resulte "
         "aplicable al Tratamiento de los Datos Personales de los Titulares.\n\n"
         "El contenido de la presente cláusula comienza a surtir sus efectos a la firma del "
         "presente contrato. No obstante, cualquiera de las Partes podrá comunicar a la otra "
         "su voluntad de concluir lo manifestado mediante previo aviso por escrito en los "
         "términos establecidos con 60 (sesenta) días naturales de anticipación a la fecha "
         "efectiva de terminación, sin necesidad de declaración o procedimiento judicial o "
         "extrajudicial alguno y sin responsabilidad para las Partes. En este último caso, "
         "las Partes acuerdan documentar el tratamiento de los datos personales y las "
         "obligaciones al respecto que les correspondan.\n\n"
         "Ninguna de las Partes será responsable de cualquier retraso o incumplimiento en sus "
         "obligaciones señaladas y demás disposiciones legales, cuando éste sea originado "
         "directamente por caso fortuito o fuerza mayor. En tal evento, la parte que llegue a "
         "incumplir deberá notificarlo a la parte afectada dentro de los 5 (cinco) días "
         "hábiles siguientes al evento de caso fortuito o fuerza mayor, para reprogramar el "
         "cumplimiento sin responsabilidad para ninguna de las partes.\n\n"
         "Las Partes convienen que la nulidad, invalidez, ilegalidad y/o cualquier otro vicio "
         "en las disposiciones manifestadas sólo afectará a dicha disposición; por lo que no "
         "afectará a las demás disposiciones aquí pactadas, las cuales, conservarán su fuerza "
         "vinculativa."),

        ("VIGÉSIMA QUINTA. - MODIFICACIÓN A LA LEGISLACIÓN",
         "Si la legislación o al marco jurídico aplicable que rige a este Contrato se "
         "modificara durante la vigencia del mismo y ello implicara algún cambio en los "
         "términos y condiciones pactados por las Partes, éstas acuerdan en someterse a "
         "dichos cambios sin que sea necesario celebrar un convenio modificatorio al Contrato "
         "para reflejarlos.\n\n"
         "En caso de que la legislación forzosamente requiriera la suscripción de documentos "
         "adicionales para el establecimiento de las nuevas condiciones, las Partes podrán "
         "celebrar convenios modificatorios o suscribir Anexos complementarios al Contrato.\n\n"
         "Si alguna de las Partes decidiera no aceptar los cambios en los términos y "
         "condiciones impuestos por la legislación aplicable, podrá dar por terminado el "
         "presente Contrato mediante notificación por escrito a la otra parte con por lo "
         "menos 60 (sesenta) días naturales de anticipación, sin responsabilidad alguna."),

        ("VIGÉSIMA SEXTA. – CUMPLIMIENTO EN MATERIA DE PREVENCIÓN DE LAVADO DE DINERO Y "
         "OBLIGACIONES DE IDENTIFICACIÓN",
         "EL CLIENTE reconoce expresamente que, derivado de la naturaleza de los servicios "
         "objeto del presente Contrato, consistentes en la comercialización, administración y "
         "operación de instrumentos de almacenamiento de valor monetario bajo la modalidad de "
         "monederos electrónicos NEA CONTROL, resulta indispensable la observancia estricta "
         "de las disposiciones aplicables en materia de prevención de operaciones con "
         "recursos de procedencia ilícita y, en su caso, financiamiento al terrorismo. En "
         "consecuencia, EL CLIENTE se obliga, bajo su más estricta responsabilidad, a llevar "
         "a cabo la identificación plena, correcta, suficiente y actualizada de todos y cada "
         "uno de los USUARIOS que designe para el uso de los monederos electrónicos, así como "
         "a verificar la licitud de los recursos que destine a la operación de dichos "
         "instrumentos, garantizando en todo momento que éstos provienen de fuentes lícitas.\n\n"
         "EL CLIENTE se obliga a recabar, conservar y mantener debidamente integrada la "
         "información y documentación de identificación de sus USUARIOS, incluyendo aquella "
         "relativa a su identidad, actividad u ocupación, perfil transaccional, así como "
         "cualquier otro dato que resulte exigible conforme a la Ley Federal para la "
         "Prevención e Identificación de Operaciones con Recursos de Procedencia Ilícita, su "
         "Reglamento, las Reglas de Carácter General que de ésta emanen, y demás disposiciones "
         "aplicables. Dicha obligación subsistirá durante toda la vigencia del presente "
         "Contrato y por el plazo de conservación legal correspondiente, aun después de su "
         "terminación.\n\n"
         "Asimismo, EL CLIENTE se obliga a proporcionar de manera completa, veraz, oportuna y "
         "verificable a NEA CONTROL, cuando ésta lo solicite y sin necesidad de requerimiento "
         "judicial o administrativo previo, toda aquella información, documentación, datos o "
         "aclaraciones que resulten necesarias o convenientes para dar cumplimiento a las "
         "obligaciones legales y regulatorias a cargo de NEA CONTROL, incluyendo, de manera "
         "enunciativa mas no limitativa, información relativa a los USUARIOS, a los "
         "beneficiarios finales o beneficiarios controladores, al origen y destino de los "
         "recursos, a la finalidad de las operaciones y a cualquier operación, transacción o "
         "patrón de uso que pudiera resultar inusual, relevante o atípico.\n\n"
         "EL CLIENTE reconoce y acepta que NEA CONTROL podrá, en cualquier momento y a su "
         "entera discreción, abstenerse de realizar dispersión de fondos, suspender "
         "temporalmente la operación de uno o varios monederos electrónicos, limitar montos, "
         "cancelar transacciones o incluso dar por terminado el presente Contrato de forma "
         "inmediata, cuando: (i) la información proporcionada resulte incompleta, "
         "inconsistente o falsa; (ii) EL CLIENTE incumpla con las obligaciones de "
         "identificación aquí previstas; o (iii) a juicio razonable de NEA CONTROL exista un "
         "riesgo legal, regulatorio, operativo o reputacional derivado del uso de los "
         "monederos electrónicos, sin que ello genere responsabilidad alguna para NEA "
         "CONTROL.\n\n"
         "EL CLIENTE libera y mantendrá en paz y a salvo a NEA CONTROL, a sus accionistas, "
         "consejeros, directivos, empleados y proveedores, frente a cualquier reclamación, "
         "procedimiento, sanción, multa, requerimiento o acción de carácter administrativo, "
         "fiscal, penal o de cualquier otra naturaleza, que derive directa o indirectamente "
         "del incumplimiento de las obligaciones asumidas en la presente cláusula, "
         "incluyendo aquellas relacionadas con la incorrecta identificación de USUARIOS, la "
         "omisión o falsedad de información, o el uso indebido de los monederos electrónicos "
         "para fines distintos a los permitidos conforme al presente Contrato y la "
         "legislación aplicable.\n\n"
         "Las obligaciones previstas en la presente cláusula se consideran esenciales para la "
         "celebración del Contrato, por lo que su incumplimiento constituirá causa grave de "
         "rescisión, sin responsabilidad alguna para NEA CONTROL, y sin perjuicio del "
         "ejercicio de las acciones legales que en derecho correspondan."),

        ("VIGÉSIMA SÉPTIMA. – DOMICILIOS Y COMUNICACIONES",
         "Toda notificación que deba hacerse con respecto a este Contrato deberá realizarse "
         "por escrito, incluyendo los correos electrónicos señalados a continuación.\n\n"
         "Las Partes señalan como domicilios para recibir documentos y/o notificaciones los "
         "especificados en el Anexo A, Formato de Alta de Clientes, siendo para NEA CONTROL: "
         "Calle 3 Picos 65, Polanco V Secc, Miguel Hidalgo, Ciudad de México, CP 11560. "
         "Teléfonos: +52 1 55 3931 5056. Correo electrónico: soporte@nea-control.com\n\n"
         "EL CLIENTE y/o los USUARIOS podrán utilizar como medio de comunicación el "
         "Call-Center de NEA a que hace referencia la Cláusula Décima Primera, salvo que el "
         "presente Contrato, sus Anexos o los términos y condiciones del Portal, del Sistema "
         "o de los monederos NEA CONTROL indiquen que, para que las comunicaciones y "
         "notificaciones se entiendan como oficiales y válidas, se realicen por otro medio.\n\n"
         "En caso de que cualquiera de las partes varíe su domicilio o correos electrónicos "
         "de contacto sin notificar con por lo menos 72 horas (setenta y dos) de anticipación "
         "a la otra parte, tendrá como efecto que las notificaciones o comunicaciones "
         "transmitidas a los domicilios y correos electrónicos anteriores se tendrán como "
         "válidas y surtirán todos sus efectos legales."),

        ("VIGÉSIMA OCTAVA. - ACUERDO NEA",
         "Las Partes reconocen que el presente Contrato y sus Anexos constituyen la totalidad "
         "del acuerdo al que las mismas han llegado respecto al objeto de los Servicios, por "
         "lo que lo aquí pactado sustituye y cancela cualquier otro acuerdo, negociación, "
         "contrato o cotización que anteriormente haya sido suscrito por las Partes."),

        ("VIGÉSIMA NOVENA. - ENCABEZADOS",
         "Las Partes manifiestan que los títulos de las Cláusulas de este Contrato se "
         "utilizan solamente como referencia, por lo que no podrán ser utilizados para la "
         "interpretación del contenido de éstas."),

        ("TRIGÉSIMA. - MODIFICACIONES",
         "Salvo lo establecido en la Cláusula Vigésima Cuarta, las Partes acuerdan que "
         "cualquier modificación a los términos y condiciones del Contrato y sus Anexos, "
         "deberá constar por escrito y estar suscrito debidamente por sus representantes "
         "legales."),

        ("TRIGÉSIMA PRIMERA. - JURISDICCIÓN y CONTROVERSIAS",
         "Las Partes acuerdan en someterse, para la interpretación y cumplimiento del "
         "Contrato, al procedimiento de conciliación ante la Procuraduría Federal del "
         "Consumidor. En caso de no existir conciliación, las Partes se someterán "
         "expresamente a la jurisdicción de los tribunales competentes en la Ciudad de "
         "México, renunciando a la jurisdicción que por razón del territorio o de sus "
         "domicilios actuales o futuros pudiere corresponderles.\n\n"
         "ENTERADAS LAS PARTES DEL CONTENIDO Y ALCANCE LEGAL DE ESTE CONTRATO, LO FIRMAN EN "
         "LA FECHA INDICADA EN EL ANEXO A, FORMATO DE ALTA DE CLIENTES."),
    ]

    S = _estilos()
    out = []
    for titulo, texto in CONTENIDO:
        if titulo == "__seccion__":
            out.append(Spacer(1, 4))
            out.append(Paragraph(texto, S["seccion"]))
            out.append(Spacer(1, 4))
            continue
        if titulo is not None:
            out.append(Paragraph(titulo, S["clausula"]))
        for parrafo in texto.split("\n\n"):
            out.append(Paragraph(parrafo, S["justo"]))
            out.append(Spacer(1, 3))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Firma NEA / EL CLIENTE (antes del Anexo A) y Anexo A
# ─────────────────────────────────────────────────────────────────────────────
def _firma_nea(S):
    return KeepTogether([
        Spacer(1, 10),
        _barra("GRIT MOBILITY, S.A. DE C.V.", S),
        Spacer(1, 16),
        Paragraph("_______________________________", S["firma"]),
        Paragraph(NEA_REPRESENTANTE, S["firma"]),
        Paragraph("Representante Legal", S["firma_sub"]),
        Spacer(1, 10),
    ])


def _firma_cliente(D, S):
    reps = D.get("representantes") or []
    celdas = []
    for i in range(3):
        nombre = reps[i]["nombre"] if i < len(reps) else None
        celdas.append([
            Paragraph("_______________________________", S["firma"]),
            Paragraph(nombre or "—", S["firma"]),
            Paragraph("Representante Legal %d%s" % (i + 1, "" if i == 0 else " (según Anexo A, si aplica)"),
                      S["firma_sub"]),
        ])
    t = Table([[c[0] for c in celdas], [c[1] for c in celdas], [c[2] for c in celdas]],
              colWidths=[ANCHO_UTIL / 3] * 3)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return KeepTogether([_barra("EL CLIENTE", S), Spacer(1, 16), t, Spacer(1, 10)])


def _domicilio_o_guion(dom, campo):
    if not dom:
        return "—"
    return dom.get(campo) or "—"


def _anexo_a(D, S):
    out = [
        Paragraph("ANEXO A", S["clausula"]),
        Paragraph("FORMATO DE ALTA DE CLIENTES", S["clausula"]),
        Paragraph("Que celebran, por una parte, <b>GRIT MOBILITY, S.A. DE C.V.</b>, representada "
                 "en este acto por %s, y la empresa cuya razón social, representante legal y "
                 "demás datos de identificación se especifican a continuación, en lo sucesivo, "
                 "el «EL CLIENTE», de forma conjunta como «LAS PARTES»." % NEA_REPRESENTANTE,
                 S["justo"]),
        Spacer(1, 6),
    ]

    es_pfae = D.get("tipo_persona") == "pfae"
    tipo_persona_txt = ("PERSONA FÍSICA CON ACTIVIDAD EMPRESARIAL" if es_pfae
                        else "PERSONA MORAL")

    out.append(_barra("MOVIMIENTO: ALTA", S))
    out.append(Spacer(1, 4))
    out.append(_campos([
        ("Modelo de Negocio", D.get("modelo_negocio")),
        ("Tipo de Persona", tipo_persona_txt),
    ], S))
    out.append(Spacer(1, 6))

    out.append(_barra("DATOS DEL CLIENTE", S))
    out.append(Spacer(1, 4))
    out.append(_campos([
        ("Razón Social", D.get("razon_social")),
        ("Nombre Comercial", D.get("nombre_comercial")),
        ("RFC", D.get("rfc_empresa")),
        ("Actividad o Giro", D.get("actividad_giro")),
        ("Nacionalidad (Persona física)", D.get("nacionalidad") if es_pfae else "—"),
    ], S))
    out.append(Spacer(1, 6))

    con = D.get("constitucion") or {}
    out.append(_barra("DATOS DE CONSTITUCIÓN DEL CLIENTE", S))
    out.append(Spacer(1, 4))
    out.append(_campos([
        ("No. Escritura Constitutiva", con.get("no_escritura")),
        ("Fecha de Constitución", con.get("fecha")),
        ("Notario", con.get("notario")),
        ("No. Notaría y Ubicación", con.get("notaria_ubicacion")),
        ("Folio RPC", con.get("folio_rpc")),
        ("Fecha de Inscripción RPC", con.get("fecha_inscripcion_rpc")),
    ], S))
    out.append(Spacer(1, 6))

    reps = D.get("representantes") or []
    out.append(_barra("REPRESENTANTE(S) LEGAL(ES) DEL CLIENTE", S))
    out.append(Spacer(1, 4))
    for i in range(3):
        r = reps[i] if i < len(reps) else {}
        out.append(_campos([
            ("Representante %d — Nombre" % (i + 1), r.get("nombre")),
            ("Escritura (Poderes)", r.get("escritura")),
            ("Notario", r.get("notario")),
            ("No. Notaría y Ubicación", r.get("notaria")),
        ], S))
    out.append(Spacer(1, 6))

    ctc = D.get("contacto") or {}
    out.append(_barra("INFORMACIÓN DE CONTACTO", S))
    out.append(Spacer(1, 4))
    out.append(_campos([
        ("Nombre del Contacto", ctc.get("nombre")),
        ("Teléfono 1", ctc.get("telefono_1")),
        ("Teléfono 2", ctc.get("telefono_2")),
        ("Correo(s) Electrónico(s)", ctc.get("correo")),
    ], S))
    out.append(Spacer(1, 6))

    dom = D.get("domicilio_fiscal") or {}
    out.append(_barra("DOMICILIO FISCAL DEL CLIENTE", S))
    out.append(Spacer(1, 4))
    out.append(_campos([
        ("Calle", dom.get("calle")), ("Número Exterior", dom.get("num_ext")),
        ("Número Interior", dom.get("num_int")), ("Colonia", dom.get("colonia")),
        ("Código Postal", dom.get("cp")), ("Municipio/Alcaldía", dom.get("municipio")),
        ("Estado", dom.get("estado")),
    ], S))
    out.append(Spacer(1, 6))

    entrega = D.get("domicilio_entrega") or dom
    out.append(_barra("DOMICILIO ENTREGA DE TARJETAS (SI NO ES EL MISMO QUE EL FISCAL)", S))
    out.append(Spacer(1, 4))
    out.append(_campos([
        ("Calle", entrega.get("calle")), ("Número Exterior", entrega.get("num_ext")),
        ("Número Interior", entrega.get("num_int")), ("Colonia", entrega.get("colonia")),
        ("Código Postal", entrega.get("cp")), ("Municipio/Alcaldía", entrega.get("municipio")),
        ("Estado", entrega.get("estado")),
    ], S))
    out.append(Spacer(1, 6))

    out.append(_barra("CONDICIONES COMERCIALES", S))
    out.append(Spacer(1, 4))
    out.append(_campos([
        ("Comisión sobre monto depositado (%)", D.get("comision")),
        ("Cuota Anual o Mensual", D.get("cuota")),
        ("Costo por Tarjeta", D.get("costo_tarjeta")),
        ("Fecha Firma de Contrato", D.get("fecha_firma_larga")),
        ("Comentarios", D.get("comentarios")),
    ], S))
    out.append(Spacer(1, 8))

    if es_pfae:
        out.append(Paragraph("<b>DOCUMENTOS ANEXOS PERSONA FÍSICA CON ACTIVIDAD EMPRESARIAL</b>",
                             S["cuerpo"]))
        for d in ("Cedula de RFC completa (Cedula de Identificación Fiscal).",
                  "Comprobante de domicilio vigente (No más de 3 meses de antigüedad).",
                  "Identificación oficial de titular.", "Formato de Alta de Clientes."):
            out.append(Paragraph("- %s" % d, S["cuerpo"]))
    else:
        out.append(Paragraph("<b>DOCUMENTOS ANEXOS PERSONA MORAL</b>", S["cuerpo"]))
        for d in ("Cedula de RFC completa (Cedula de Identificación Fiscal).",
                  "Comprobante de domicilio vigente (No más de 3 meses de antigüedad).",
                  "Acta Constitutiva.", "Poder Notarial con actos administrativos o de dominio.",
                  "Identificación oficial de apoderado legal ambos lados.",
                  "Formato de Alta de Clientes."):
            out.append(Paragraph("- %s" % d, S["cuerpo"]))

    return out


def _pie_pagina(canv, doc):
    canv.saveState()
    canv.setStrokeColor(NEA_CORAL)
    canv.setLineWidth(1.2)
    canv.line(MARGEN, 12 * mm, letter[0] - MARGEN, 12 * mm)
    canv.setFont("Helvetica", 6.5)
    canv.setFillColor(colors.HexColor("#555555"))
    canv.drawString(MARGEN, 8.5 * mm, "Contrato de Prestación de Servicios — Grit Mobility, S.A. de C.V.")
    canv.drawRightString(letter[0] - MARGEN, 8.5 * mm, "Página %d" % canv.getPageNumber())
    canv.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def generar_contrato_grit(datos: dict, output_path: str):
    """Genera el Contrato de Prestación de Servicios de Grit Mobility."""
    D = dict(datos)
    S = _estilos()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = BaseDocTemplate(output_path, pagesize=letter,
                          leftMargin=MARGEN, rightMargin=MARGEN,
                          topMargin=MARGEN, bottomMargin=18 * mm,
                          title="Contrato de Prestación de Servicios — Grit Mobility, S.A. de C.V.",
                          author="Grit Mobility, S.A. de C.V.")
    frame = Frame(MARGEN, 18 * mm, ANCHO_UTIL, letter[1] - MARGEN - 18 * mm, id="cuerpo",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=_pie_pagina)])

    story = []
    story += _clausulado()
    story.append(_firma_nea(S))
    story.append(_firma_cliente(D, S))
    story += _anexo_a(D, S)

    doc.build(story)
    print("Contrato de Grit Mobility generado: %s" % output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        generar_contrato_grit(json.load(fh), sys.argv[2])
