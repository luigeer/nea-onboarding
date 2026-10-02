# -*- coding: utf-8 -*-
"""
Pruebas de la Autorización para solicitar Reportes de Crédito (persona moral).

Es el formato con el que el cliente autoriza a Grit Payment Solutions a
consultarlo en Buró. Un renglón vacío o con el dato de otro cliente no se nota
al firmar, se nota cuando Buró audita la consulta: por eso se prueba que cada
dato del expediente llegue a su renglón, que el PDF salga sin campos editables
—nadie debe poder cambiar un dato ya firmado— y que el formato solo salga donde
aplica.

Todos los datos son inventados.

Se corre con:
    python tests/test_autorizacion_buro.py
"""

import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "generadores"))
sys.path.insert(0, os.path.join(RAIZ, "tests"))

import pdfplumber
from pypdf import PdfReader

import firma
import verificador
from adaptadores import ADAPTADORES, campos_en_blanco
from fixture_paquete import copia, persona_moral
from generar_paquete import ASSETS, CATALOGO, _firmantes
from schema_expediente import documentos_aplicables

fallas = []
TEMPLATE = os.path.join(ASSETS, "Autorizacion_Buro_PM_Template.pdf")


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def expediente():
    e = persona_moral()
    e["cliente"]["validado"]["domicilio"].update(
        {"calle": "PROL P DE LA REFORMA", "num_ext": "1725", "num_int": "B 25 Y 26",
         "colonia": "LOMA DE PALO ALTO", "cp": "05110",
         "municipio": "CUAJIMALPA DE MORELOS"})
    e["representante_legal"]["propuesto"]["correo"] = "carlos@ejemplo.mx"
    return e


def generar(exp, carpeta):
    fn, template = CATALOGO["autorizacion_buro"][1], CATALOGO["autorizacion_buro"][2]
    ruta = os.path.join(carpeta, "T-01_Autorizacion_Buro.pdf")
    fn(ADAPTADORES["autorizacion_buro"](exp), ruta, os.path.join(ASSETS, template))
    return ruta


def texto(ruta):
    """Solo lo que escribió el generador (Helvetica). La plantilla dibuja sus
    renglones con guiones bajos y, leídos juntos, se intercalan con el dato."""
    with pdfplumber.open(ruta) as pdf:
        return " ".join(p.filter(verificador._es_del_sistema).extract_text() or ""
                        for p in pdf.pages)


def test_la_plantilla_en_blanco_esta_en_assets():
    check(os.path.exists(TEMPLATE), "assets/Autorizacion_Buro_PM_Template.pdf existe")


def test_cada_dato_del_expediente_llega_a_su_renglon():
    with tempfile.TemporaryDirectory() as tmp:
        t = texto(generar(expediente(), tmp))
    for valor in ("EJEMPLO INDUSTRIAL, S.A. de C.V.", "CARLOS RUIZ LOPEZ",
                  "EJE200803A2A", "PROL P DE LA REFORMA 1725", "B 25 Y 26",
                  "LOMA DE PALO ALTO", "CUAJIMALPA DE MORELOS",
                  "CIUDAD DE MEXICO", "05110", "5500000000",
                  "25 de septiembre de 2026", "carlos@ejemplo.mx"):
        check(valor in t, "el PDF trae %r" % valor)


def test_el_pdf_sale_sin_campos_editables():
    with tempfile.TemporaryDirectory() as tmp:
        r = PdfReader(generar(expediente(), tmp))
        campos = r.get_fields() or {}
        anotaciones = [a for p in r.pages for a in (p.get("/Annots") or [])
                       if a.get_object().get("/FT")]
    check(not campos and not anotaciones,
          "no quedan campos editables (hay %d)" % (len(campos) + len(anotaciones)))


def test_un_dato_faltante_se_avisa_como_campo_en_blanco():
    e = expediente()
    e["cliente"]["validado"]["telefono"] = None
    e["representante_legal"]["propuesto"]["correo"] = None
    vacios = campos_en_blanco(e, "autorizacion_buro")
    check("telefono" in vacios, "el teléfono faltante se avisa (%r)" % vacios)
    check("correo_representante" in vacios,
          "el correo faltante se avisa (%r)" % vacios)
    with tempfile.TemporaryDirectory() as tmp:
        generar(e, tmp)
    check(True, "con datos faltantes el documento se genera igual")


def test_sale_en_persona_moral_y_no_en_persona_fisica():
    check("autorizacion_buro" in documentos_aplicables(expediente()),
          "la persona moral lleva autorización de buró")
    pf = copia(expediente())
    pf["tipo_cliente"] = "persona_fisica"
    check("autorizacion_buro" not in documentos_aplicables(pf),
          "la persona física no lleva la de persona moral")


def test_solo_firma_el_representante_legal():
    f = _firmantes("autorizacion_buro", expediente())
    check([x["rol"] for x in f] == ["cliente"],
          "solo firma el cliente (%r)" % [x["rol"] for x in f])
    check(f[0]["nombre"] == "CARLOS RUIZ LOPEZ", "firma el representante legal")


def test_va_en_su_propia_division_de_weetrust():
    check("autorizacion_buro" in firma.ORDEN, "está en el orden del PDF de firma")
    man = {"documentos": [
        {"clave": "contrato", "archivo": "c.pdf", "firmantes": []},
        {"clave": "autorizacion_buro", "archivo": "b.pdf", "firmantes": []}]}
    divisiones = [d["division"] for d in firma.plan(man)["divisiones"]]
    check("Autorización de consulta a Buró" in divisiones,
          "tiene su división (%r)" % divisiones)


def test_el_verificador_la_revisa():
    e = expediente()
    with tempfile.TemporaryDirectory() as tmp:
        ruta = generar(e, tmp)
        bien = verificador.verificar_documento("autorizacion_buro", ruta, e)
        otro = copia(e)
        otro["cliente"]["validado"]["rfc"] = "OTR010101AAA"
        mal = verificador.verificar_documento("autorizacion_buro", ruta, otro)
    check(bien == [], "un documento correcto no tiene hallazgos (%r)" % bien)
    check(any(h["regla"] == "dato" for h in mal),
          "si el RFC impreso no es el del expediente, lo detecta")


def main():
    test_la_plantilla_en_blanco_esta_en_assets()
    test_cada_dato_del_expediente_llega_a_su_renglon()
    test_el_pdf_sale_sin_campos_editables()
    test_un_dato_faltante_se_avisa_como_campo_en_blanco()
    test_sale_en_persona_moral_y_no_en_persona_fisica()
    test_solo_firma_el_representante_legal()
    test_va_en_su_propia_division_de_weetrust()
    test_el_verificador_la_revisa()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
