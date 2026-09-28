# -*- coding: utf-8 -*-
"""
verificador.py — Revisión de los PDFs ya generados contra el expediente
=========================================================================
Las compuertas revisan el expediente antes de generar. Esto revisa lo que salió:
el PDF que va a firmar el cliente. Los errores que motivaron este módulo no
eran de datos mal capturados sino de cómo se armaba el documento (una etiqueta
fija, una coordenada, una clave que el generador no reconocía), así que solo se
ven leyendo el PDF.

Reglas:
  empresa         un documento nombra solo a su sujeto obligado
  oficial         el Formato BC lleva al oficial de cumplimiento de su empresa
  firma           en el contrato, la persona va en "Nombre:" y la sociedad en
                  "Apoderado de:"
  identificacion  en el PLD hay una sola casilla de identificación marcada y es
                  la del expediente
  dato            RFC, razón social, línea y demás datos clave aparecen en el
                  documento y coinciden con el expediente

generar_paquete deja el resultado en el manifiesto; subir y firma se niegan a
avanzar con un paquete que tiene hallazgos o que nunca se verificó.
"""

import json
import os
import re
import unicodedata
from datetime import date

import pdfplumber

from adaptadores import (ADAPTADORES, GRIT_RESPONSABLE_CUMPLIMIENTO,
                         NEA_RESPONSABLE_CUMPLIMIENTO)
from schema_expediente import _get

NEA = {"contrato", "contrato_pfae", "pld_pm", "pld_pf", "beneficiario_controlador"}
GRIT = {"grit_contrato", "grit_pld_pm", "grit_pld_pf", "grit_beneficiario_controlador"}
PLD = {"pld_pm", "pld_pf", "grit_pld_pm", "grit_pld_pf"}
CONTRATOS_CON_LINEA = {"contrato", "contrato_pfae"}

# Última palabra de la etiqueta impresa junto a cada casilla -> clave del adaptador.
_ETIQUETA_ID = {"IFE": "ife", "PASAPORTE": "pasaporte", "PROFESIONAL": "cedula",
                "LICENCIA": "licencia", "MIGRATORIO": "migratorio"}

# Campos del dict del adaptador que tienen que aparecer impresos en el PDF.
_CAMPOS_DATO = {
    "contrato": ["rfc_empresa", "razon_social", "linea_credito", "mensualidad"],
    "contrato_pfae": ["rfc", "nombre_pf", "linea_credito", "mensualidad"],
    "grit_contrato": ["rfc_empresa", "razon_social"],
    "pld_pm": ["rfc_empresa", "razon_social", "nombre_rep", "num_id"],
    "grit_pld_pm": ["rfc_empresa", "razon_social", "nombre_rep", "num_id"],
    "pld_pf": ["rfc", "nombre_completo", "num_id"],
    "grit_pld_pf": ["rfc", "nombre_completo", "num_id"],
    "beneficiario_controlador": ["cliente.rfc", "cliente.razon_social"],
    "grit_beneficiario_controlador": ["cliente.rfc", "cliente.razon_social"],
}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.upper()).strip()


def _texto(ruta):
    with pdfplumber.open(ruta) as pdf:
        return _norm(" ".join(p.extract_text() or "" for p in pdf.pages))


def _es_del_sistema(obj):
    return obj["object_type"] != "char" or obj.get("fontname", "").startswith("Helvetica")


def _texto_del_sistema(ruta):
    """Solo lo que escribió el generador (Helvetica), sin la plantilla de fondo.

    En las carátulas sobre plantilla, el valor se imprime encima de un
    "$0.00 M.N." tapado con un recuadro blanco: se ve bien, pero en la capa de
    texto los dos quedan intercalados ("$$205.,0000 0M.0.NN0.").
    """
    with pdfplumber.open(ruta) as pdf:
        return _norm(" ".join(p.filter(_es_del_sistema).extract_text() or ""
                              for p in pdf.pages))


def _aparece(valor, texto):
    """Cada palabra del valor está en el texto: tolera saltos de línea y celdas."""
    palabras = _norm(valor).split()
    return bool(palabras) and all(p in texto for p in palabras)


def _hallazgo(clave, ruta, regla, detalle):
    return {"clave": clave, "archivo": os.path.basename(ruta), "regla": regla,
            "detalle": detalle}


def casillas_de_identificacion(ruta):
    """Claves de las casillas de identificación marcadas, o None si no está el renglón."""
    with pdfplumber.open(ruta) as pdf:
        for page in pdf.pages:
            palabras = page.extract_words()
            for pas in (w for w in palabras if w["text"] == "PASAPORTE"):
                fila = [w for w in palabras if abs(w["top"] - pas["top"]) < 3]
                if "LICENCIA" not in {w["text"] for w in fila}:
                    continue
                marcadas = set()
                for w in fila:
                    clave = _ETIQUETA_ID.get(w["text"])
                    if clave and any(ch["text"] == "X" and abs(ch["top"] - w["top"]) < 4
                                     and w["x1"] < ch["x0"] < w["x1"] + 20
                                     for ch in page.chars):
                        marcadas.add(clave)
                return marcadas
    return None


def _renglon_de(palabras, etiqueta):
    """Texto impreso a la derecha de la etiqueta, en su mismo renglón."""
    et = next((w for w in palabras if w["text"] == etiqueta and w["x0"] < 320), None)
    if et is None:
        return None
    return _norm(" ".join(w["text"] for w in sorted(palabras, key=lambda w: w["x0"])
                          if 140 <= w["x0"] < 320 and abs(w["top"] - et["top"]) < 3))


def _regla_firma(clave, ruta, datos):
    with pdfplumber.open(ruta) as pdf:
        palabras = pdf.pages[0].extract_words()
    nombre = _renglon_de(palabras, "Nombre:")
    apoderado = _renglon_de(palabras, "Apoderado")
    persona, empresa = datos.get("firma_rep_legal"), datos.get("firma_razon_social")
    fuera = []
    if persona and not (nombre and _aparece(persona, nombre)):
        fuera.append("el representante (%s) no está en el renglón de 'Nombre:'" % persona)
    if empresa and not (apoderado and _aparece(empresa, apoderado)):
        fuera.append("la razón social (%s) no está en el renglón de 'Apoderado de:'" % empresa)
    return [_hallazgo(clave, ruta, "firma", "; ".join(fuera))] if fuera else []


def _valor(datos, campo):
    for parte in campo.split("."):
        datos = (datos or {}).get(parte)
    return datos


def verificar_documento(clave, ruta, exp):
    """Hallazgos de un PDF generado. Un documento sin reglas no tiene hallazgos."""
    if clave not in NEA and clave not in GRIT:
        return []
    texto = _texto(ruta)
    datos = ADAPTADORES[clave](exp)
    h = []

    otra = "GRIT PAYMENT" if clave in GRIT else "GRIT MOBILITY"
    if otra in texto:
        h.append(_hallazgo(clave, ruta, "empresa",
                           "nombra a %s, que no es el sujeto obligado de este documento"
                           % otra.title()))

    if clave in ("beneficiario_controlador", "grit_beneficiario_controlador"):
        propio = _norm((datos.get("responsable_cumplimiento") or {}).get("nombre") or "")
        ajeno = (GRIT_RESPONSABLE_CUMPLIMIENTO if clave == "beneficiario_controlador"
                 else NEA_RESPONSABLE_CUMPLIMIENTO)["nombre"]
        if _norm(ajeno) in texto:
            h.append(_hallazgo(clave, ruta, "oficial",
                               "lleva a %s, oficial de cumplimiento de la otra empresa" % ajeno))
        elif propio and propio not in texto:
            h.append(_hallazgo(clave, ruta, "oficial",
                               "no aparece su oficial de cumplimiento (%s)" % propio.title()))

    if clave == "contrato":
        h += _regla_firma(clave, ruta, datos)

    if clave in PLD:
        esperada = (datos.get("tipo_id_oficial") or "").lower().replace("ine", "ife")
        marcadas = casillas_de_identificacion(ruta)
        if marcadas is None:
            h.append(_hallazgo(clave, ruta, "identificacion",
                               "no se encontró el renglón de tipo de identificación"))
        elif marcadas != {esperada}:
            h.append(_hallazgo(clave, ruta, "identificacion",
                               "casillas marcadas %s; el expediente dice %s"
                               % (sorted(marcadas) or "ninguna", esperada)))

    sistema = _texto_del_sistema(ruta)

    def impreso(valor):
        return _aparece(valor, texto) or _aparece(valor, sistema)

    faltan = [c for c in _CAMPOS_DATO.get(clave, [])
              if _valor(datos, c) and not impreso(_valor(datos, c))]
    # El RFC y la línea se comparan también contra el expediente, no solo contra
    # lo que el adaptador le pasó al generador: si el adaptador traduce mal, el
    # PDF sale coherente consigo mismo y equivocado.
    rfc = _get(exp, "cliente.validado.rfc")
    if rfc and not impreso(rfc):
        faltan.append("RFC del expediente (%s)" % rfc)
    linea = _get(exp, "credito.autorizada.linea")
    if clave in CONTRATOS_CON_LINEA and linea and not impreso(format(float(linea), ",.2f")):
        faltan.append("línea autorizada del expediente (%s)" % format(float(linea), ",.2f"))
    if faltan:
        h.append(_hallazgo(clave, ruta, "dato",
                           "no aparece en el documento: %s" % ", ".join(faltan)))
    return h


def verificar(exp, dir_paquete, manifiesto):
    h = []
    for d in manifiesto.get("documentos", []):
        h += verificar_documento(d["clave"], os.path.join(dir_paquete, d["archivo"]), exp)
    return h


def resultado(hallazgos):
    return {"fecha": date.today().isoformat(), "ok": not hallazgos, "hallazgos": hallazgos}


def paquete_listo(dir_paquete, folio):
    """(listo, motivos). Sin verificación registrada no hay paquete listo."""
    ruta = os.path.join(dir_paquete, "%s_manifiesto.json" % folio)
    if not os.path.exists(ruta):
        return False, ["No hay manifiesto: el paquete no se generó con nea.py generar."]
    with open(ruta, encoding="utf-8") as fh:
        v = json.load(fh).get("verificacion")
    if not v:
        return False, ["El paquete se generó antes de que existiera la verificación. "
                       "Vuelve a generarlo: python nea.py generar %s" % folio]
    if not v.get("ok"):
        return False, ["%s [%s]: %s" % (x["archivo"], x["regla"], x["detalle"])
                       for x in v.get("hallazgos", [])]
    return True, []
