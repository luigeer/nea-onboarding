# -*- coding: utf-8 -*-
"""
generar_paquete.py — Etapa 6 del onboarding de Nea
===================================================
Valida las compuertas, decide qué documentos aplican, los genera y escribe el
manifiesto de firmantes.

La generación NO se dispara sola: se invoca a mano una vez que la línea autorizada
está registrada en el expediente.

Salida: archivos separados con convención FOLIO_Documento.pdf, más manifiesto.json.

El manifiesto agrupa los documentos por conjunto de firmantes. Hoy sirve como
lista de control para la firma; el día que se integre la firma electrónica, la
integración lee este archivo en lugar de volver a deducir quién firma qué.

Uso:
    python generar_paquete.py <expediente.json> <directorio_salida>
    python generar_paquete.py <expediente.json> <directorio_salida> --solo-compuertas
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "generadores"))

from schema_expediente import (compuertas_generacion, documentos_aplicables, _get)
from adaptadores import ADAPTADORES

from generar_contrato import fill_contrato
from generar_contrato_pfae import fill_contrato_pfae
from generar_pld import generar_pld
from generar_pld_pf import generar_pld_pf
from generar_beneficiario import generar_beneficiario
from generar_anexo_razonado import generar_anexo_razonado
from generar_adenda import generar_adenda
from generar_adenda_pf import generar_adenda_pf
from generar_domiciliacion import generar_domiciliacion

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")

NEA_FIRMANTE = {"rol": "nea", "nombre": "Marcos Siqueiros Ballesteros",
                "cargo": "Representante Legal de Grit Payment Solutions, S.A.P.I. de C.V."}

# El Oficial de Cumplimiento es uno en la empresa, no uno por cliente. Vivia como
# campo del expediente y por eso pudo quedar mal en un expediente: la compuerta
# pedia un nombre, alguien lo lleno a mano y nadie lo comparo contra nada. Aqui
# hay una sola copia; el campo del expediente solo sirve para el caso en que
# firme alguien distinto, y entonces es una excepcion explicita.
NEA_CUMPLIMIENTO = {"rol": "cumplimiento", "nombre": "Marcos Siqueiros Ballesteros",
                    "cargo": "Oficial de Cumplimiento"}

# clave -> (sufijo del archivo, función generadora, template o None, etiqueta)
CATALOGO = {
    "contrato": ("Contrato", fill_contrato, "Contrato_Vacio.pdf",
                 "Carátula del Contrato de Crédito"),
    "contrato_pfae": ("Contrato", fill_contrato_pfae, "Contrato_Vacio_PFAE.pdf",
                      "Carátula del Contrato de Crédito (persona física)"),
    "pld_pm": ("PLD", generar_pld, None,
               "Formato de Identificación PLD (Anexo 4, persona moral)"),
    "pld_pf": ("PLD", generar_pld_pf, None,
               "Formato de Identificación PLD (Anexo 3, persona física)"),
    "beneficiario_controlador": ("Beneficiario_Controlador", generar_beneficiario, None,
                                 "Formato de Identificación del Beneficiario Controlador"),
    "anexo_razonado": ("Anexo_Analisis_Razonado", generar_anexo_razonado, None,
                       "Anexo de Análisis Razonado del Beneficiario Controlador"),
    "adenda_os_pm": ("Adenda_OS_PM", generar_adenda,
                     "Adenda_Obligado_Solidario_Template.pdf",
                     "Adenda de Obligado Solidario (persona moral)"),
    "adenda_os_pf": ("Adenda_OS_PF", generar_adenda_pf,
                     "Adenda_Obligado_Solidario_Persona_Fisica_Template.pdf",
                     "Adenda de Obligado Solidario (persona física)"),
    "domiciliacion": ("Domiciliacion", generar_domiciliacion,
                      "Formato_Domiciliacion_Template.pdf",
                      "Autorización de Domiciliación"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Firmantes por documento
# ─────────────────────────────────────────────────────────────────────────────
def _firmantes(clave, exp):
    """Quién firma cada documento. Es la única fuente de esta lógica."""
    rep = _get(exp, "representante_legal.validado", {})
    cliente = {"rol": "cliente",
               "nombre": rep.get("nombre"),
               "cargo": rep.get("cargo") or "Representante Legal",
               "correo": _get(exp, "representante_legal.propuesto.correo")}
    cofirmantes = [{"rol": "cofirmante_cliente", "nombre": c.get("nombre"),
                    "correo": c.get("correo")} for c in _get(exp, "cofirmantes", [])]
    # El Oficial de Cumplimiento sale de NEA_CUMPLIMIENTO. El expediente solo lo
    # sobreescribe si trae un nombre distinto, que es la excepcion y no la regla.
    #
    # Antes la compuerta exigia `bc_firmado_por` y el documento imprimia
    # `cumplimiento.responsable` —dos campos para lo mismo—, asi que el formato
    # que legalmente requiere esta firma salia con la linea en blanco aunque la
    # compuerta estuviera satisfecha.
    resp = _get(exp, "cumplimiento.responsable") or {}
    cumplimiento = dict(NEA_CUMPLIMIENTO)
    if resp.get("nombre"):
        cumplimiento.update({"nombre": resp["nombre"],
                             "cargo": resp.get("cargo") or NEA_CUMPLIMIENTO["cargo"]})

    if clave in ("contrato", "contrato_pfae"):
        return [cliente] + cofirmantes + [NEA_FIRMANTE]
    if clave in ("pld_pm", "pld_pf"):
        return [cliente] + cofirmantes
    if clave == "beneficiario_controlador":
        return [cliente] + cofirmantes + [cumplimiento]
    if clave == "anexo_razonado":
        # Documento interno del sujeto obligado: el cliente no lo suscribe.
        return [cumplimiento]
    if clave == "domiciliacion":
        return [cliente] + cofirmantes
    if clave == "adenda_os_pm":
        os_ = _get(exp, "obligado_solidario", {})
        return [cliente] + cofirmantes + [
            {"rol": "obligado_solidario", "nombre": os_.get("rep_legal"),
             "cargo": "Representante Legal de %s" % (os_.get("razon_social") or "")},
            NEA_FIRMANTE]
    if clave == "adenda_os_pf":
        pf = _get(exp, "obligado_solidario_pf", {}) or {}
        raiz = "obligado_solidario_pf"
        if not pf.get("nombre"):
            pf = _get(exp, "obligado_solidario.persona_fisica", {}) or {}
            raiz = "obligado_solidario"
        firmas = [cliente] + cofirmantes + [
            {"rol": "obligado_solidario", "nombre": pf.get("nombre"),
             "cargo": "Por su propio derecho", "correo": pf.get("correo")},
            NEA_FIRMANTE]
        cy = _get(exp, "%s.conyuge" % raiz)
        if cy:
            firmas.append({"rol": "conyuge", "nombre": cy.get("nombre"),
                           "cargo": "Por su propio derecho (Anexo A)"})
        return firmas
    return [cliente]


def _personas(firmantes):
    """Conjunto de personas distintas que deben firmar, sin importar la calidad.

    Una misma persona puede firmar un documento en dos calidades — el caso típico
    es el representante legal que además es obligado solidario por su propio
    derecho. Para la firma sigue siendo una sola persona.
    """
    vistos, out = set(), []
    for f in firmantes:
        n = (f.get("nombre") or "").strip()
        if n and n.lower() not in vistos:
            vistos.add(n.lower())
            out.append(n)
    return out


def _clave_grupo(firmantes):
    """Documentos que firman las mismas personas se firman en un solo acto."""
    return "|".join(sorted(n.lower() for n in _personas(firmantes)))


# ─────────────────────────────────────────────────────────────────────────────
# Orquestación
# ─────────────────────────────────────────────────────────────────────────────
def generar_paquete(exp, dir_salida, solo_compuertas=False):
    folio = exp.get("folio") or "SIN-FOLIO"

    fallas = compuertas_generacion(exp)
    if fallas:
        print("COMPUERTAS NO SUPERADAS (%d) — no se generó ningún documento:" % len(fallas))
        for f in fallas:
            print("  - %s" % f)
        return {"folio": folio, "generado": False, "fallas": fallas}
    print("Compuertas superadas.")

    claves = documentos_aplicables(exp)
    print("Documentos aplicables (%d): %s" % (len(claves), ", ".join(claves)))
    if solo_compuertas:
        return {"folio": folio, "generado": False, "documentos_aplicables": claves}

    os.makedirs(dir_salida, exist_ok=True)
    manifiesto = {"folio": folio,
                  "cliente": _get(exp, "cliente.validado.razon_social"),
                  "rfc": _get(exp, "cliente.validado.rfc"),
                  "linea_autorizada": _get(exp, "credito.autorizada.linea"),
                  "documentos": [], "grupos_de_firma": []}
    grupos = {}

    sufijos = {}
    for clave in claves:
        sufijo = CATALOGO[clave][0]
        if sufijo in sufijos:
            raise ValueError(
                "%s y %s escribirian el mismo archivo (%s). Cada documento del "
                "paquete necesita su propio nombre: si no, uno pisa al otro y el "
                "manifiesto declara mas documentos de los que existen."
                % (sufijos[sufijo], clave, sufijo))
        sufijos[sufijo] = clave

    for clave in claves:
        sufijo, fn, template, etiqueta = CATALOGO[clave]
        datos = ADAPTADORES[clave](exp)
        nombre = "%s_%s.pdf" % (folio, sufijo)
        ruta = os.path.join(dir_salida, nombre)

        if template:
            fn(datos, ruta, os.path.join(ASSETS, template))
        else:
            fn(datos, ruta)

        firmantes = _firmantes(clave, exp)
        manifiesto["documentos"].append({
            "clave": clave, "etiqueta": etiqueta, "archivo": nombre,
            "firmantes": firmantes, "grupo_firma": None,
        })
        grupos.setdefault(_clave_grupo(firmantes), []).append(clave)

    # Numerar los grupos y anotarlos en cada documento
    for i, (gk, claves_g) in enumerate(sorted(grupos.items()), start=1):
        firmantes = _firmantes(claves_g[0], exp)
        manifiesto["grupos_de_firma"].append(
            {"grupo": i, "documentos": claves_g,
             "personas": _personas(firmantes), "firmantes": firmantes})
        for d in manifiesto["documentos"]:
            if d["clave"] in claves_g:
                d["grupo_firma"] = i

    ruta_man = os.path.join(dir_salida, "%s_manifiesto.json" % folio)
    with open(ruta_man, "w", encoding="utf-8") as fh:
        json.dump(manifiesto, fh, ensure_ascii=False, indent=2)

    print("\n%d documentos generados en %s" % (len(claves), dir_salida))
    print("%d grupo(s) de firma:" % len(manifiesto["grupos_de_firma"]))
    for g in manifiesto["grupos_de_firma"]:
        quienes = ", ".join(g["personas"])
        print("  Grupo %d — %s" % (g["grupo"], quienes))
        for c in g["documentos"]:
            print("      %s_%s.pdf" % (folio, CATALOGO[c][0]))
    print("\nManifiesto: %s" % ruta_man)
    return manifiesto


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        expediente = json.load(fh)
    generar_paquete(expediente, sys.argv[2], "--solo-compuertas" in sys.argv)
