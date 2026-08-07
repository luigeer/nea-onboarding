# -*- coding: utf-8 -*-
"""
nomenclatura.py — Cómo se nombran los archivos del expediente
==============================================================
Ventas suelta los documentos con el nombre que se le ocurre, en su propia
carpeta. Nosotros no tocamos esa carpeta: **copiamos** a la nuestra y ahí sí
mandamos nosotros con el nombre.

Formato:

    TIPO_NombreComercial_QUÉFECHA-AAAA-MM-DD.pdf

Tres piezas y ninguna ambigua:

  TIPO             qué documento es
  NombreComercial  de quién es. Sin espacios ni acentos, para que el nombre
                   sobreviva a cualquier sistema
  QUÉFECHA-fecha   **la fecha viene etiquetada**, porque no significa lo mismo
                   en todos los documentos:
                     emitida-  CSF, comprobante de domicilio, buró, cotización
                     vence-    identificaciones, autorizaciones de buró
                     corte-    estados de cuenta
                     firmada-  actas, poderes, contratos

Ejemplos reales:

    CSF_LaLlosa_emitida-2026-07-01.pdf
    ComprobanteDomicilio_LaLlosa_emitida-2026-05-11.pdf
    INE_DiegoRamirez_vence-2033-12-31.pdf
    EdoCuenta_LaLlosa_BBVA_corte-2026-05-31.pdf
    ActaConstitutiva_LaLlosa_firmada-2023-09-06.pdf
    Buro_LaLlosa_emitida-2026-08-06.pdf

Por qué la etiqueta: un archivo llamado `INE_Diego_2033-12-31` se lee raro
—¿una identificación de 2033?— mientras que `INE_Diego_vence-2033-12-31` se
entiende de un vistazo. Y ordenar la carpeta por nombre agrupa por tipo, que
es como se revisa un expediente.
"""

import re
import unicodedata

# Qué fecha lleva cada tipo de documento.
EMITIDA = "emitida"
VENCE = "vence"
CORTE = "corte"
FIRMADA = "firmada"

TIPOS = {
    "csf":                  ("CSF", EMITIDA),
    "comprobante_domicilio": ("ComprobanteDomicilio", EMITIDA),
    "identificacion":       ("INE", VENCE),
    "pasaporte":            ("Pasaporte", VENCE),
    "autorizacion_buro":    ("AutorizacionBuro", VENCE),
    "buro":                 ("Buro", EMITIDA),
    "estado_cuenta":        ("EdoCuenta", CORTE),
    "acta_constitutiva":    ("ActaConstitutiva", FIRMADA),
    "acta_asamblea":        ("ActaAsamblea", FIRMADA),
    "poder":                ("Poder", FIRMADA),
    "cotizacion":           ("Cotizacion", EMITIDA),
    "credencial_sat":       ("CredencialSAT", EMITIDA),
    "constancia_cuenta_propia": ("ConstanciaCuentaPropia", FIRMADA),
    "caratula_bancaria":    ("CaratulaBancaria", EMITIDA),
}


def compacto(texto):
    """'LA LLOSA SUPPLIER, S.A. de C.V.' -> 'LaLlosaSupplier'.

    Se quitan acentos, sufijos societarios y todo lo que no sea letra o
    número. El resultado va en el nombre de archivo, así que tiene que
    sobrevivir a Windows, a Drive y a un correo.
    """
    if not texto:
        return "SinNombre"
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    # El sufijo societario se corta antes de separar en palabras: partir
    # 'S.A.P.I. de C.V.' por los puntos deja letras sueltas que se pegarían al
    # nombre como basura ('GritPaymentSolutionsPI').
    t = re.split(r"[,;]|\bS\s*\.?\s*A\s*\.?\s*P\s*\.?\s*I\b|\bS\s*\.?\s*A\s*\.?\s*B\b"
                 r"|\bS\s*\.?\s*A\b|\bS\s*\.?\s*C\b|\bS\s*\.?\s*A\s*\.?\s*S\b"
                 r"|\bA\s*\.?\s*C\b|\bS\s*\.?\s+de\s+R\s*\.?\s*L\b",
                 t, maxsplit=1, flags=re.I)[0]
    t = re.sub(r"[^\w\s]", " ", t)
    # Conectores que nunca distinguen a nadie.
    ruido = {"DE", "DEL", "Y", "CV", "SA", "SC", "RL", "SAPI", "SAS", "AC",
             "COOPERATIVA", "SOCIEDAD", "ANONIMA"}
    # Un artículo al inicio sí es parte del nombre —La Llosa, El Cabrerío, Los
    # Oyameles— pero a media razón social sobra.
    articulos = {"LA", "LAS", "LOS", "EL"}

    palabras = []
    for i, p in enumerate(t.split()):
        arriba = p.upper()
        if arriba in ruido or len(p) < 2 or p.isdigit():
            continue
        if arriba in articulos and palabras:
            continue
        palabras.append(p)
    return "".join(p[:1].upper() + p[1:].lower() for p in palabras) or "SinNombre"


def nombre_archivo(tipo, sujeto, fecha, banco=None, extension="pdf", sufijo=None):
    """Arma el nombre canónico de un documento del expediente.

    `fecha` es la que corresponda al tipo: de emisión, de vencimiento o de
    corte. Si no se conoce, se marca como `sin-fecha` para que salte a la vista
    en la carpeta en lugar de esconderse.
    """
    if tipo not in TIPOS:
        raise ValueError(
            "Tipo de documento desconocido: %r. Los válidos son: %s"
            % (tipo, ", ".join(sorted(TIPOS))))
    etiqueta_tipo, que_fecha = TIPOS[tipo]

    partes = [etiqueta_tipo, compacto(sujeto)]
    if banco:
        partes.append(compacto(banco))
    if sufijo:
        partes.append(compacto(sufijo))
    partes.append("%s-%s" % (que_fecha, fecha) if fecha else "sin-fecha")
    return "%s.%s" % ("_".join(partes), extension.lstrip("."))


def que_fecha_lleva(tipo):
    """Para preguntarle a quien captura: '¿qué fecha necesito de este documento?'"""
    if tipo not in TIPOS:
        return None
    return {EMITIDA: "fecha de emisión",
            VENCE: "fecha de vencimiento",
            CORTE: "fecha de corte",
            FIRMADA: "fecha de firma"}.get(TIPOS[tipo][1], "fecha del documento")
