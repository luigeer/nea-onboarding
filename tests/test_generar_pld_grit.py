# -*- coding: utf-8 -*-
"""
Pruebas de generar_pld.py: el sujeto obligado (nombre, domicilio, actividad
vulnerable que encabeza el formulario) debe poder sobreescribirse por datos,
para poder emitir el mismo Anexo 4 a nombre de Grit Mobility en vez de Nea.

Se corre con:
    python tests/test_generar_pld_grit.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generadores"))

import pdfplumber

from generar_pld import generar_pld
from generar_pld_pf import generar_pld_pf

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


DATOS_BASE = {
    "fecha_operacion": "24/03/2026",
    "razon_social": "EMPRESA, S.A. DE C.V.",
    "fecha_constitucion": "31/08/2012",
    "pais_nacionalidad": "México",
    "rfc_empresa": "RFC123456XXX",
    "actividad_giro": "Venta de combustibles automotrices",
    "calle": "AV. GOBERNADORES",
    "num_ext": "46",
    "colonia": "BURÓCRATAS",
    "cp": "39090",
    "municipio": "CHILPANCINGO DE LOS BRAVO",
    "estado": "GUERRERO",
    "pais_domicilio": "México",
    "telefono": "7471162651",
    "correo": "correo@empresa.mx",
    "nombre_rep": "APELLIDO_PAT APELLIDO_MAT NOMBRE",
    "fecha_nac_rep": "07/07/1951",
    "pais_nac_rep": "México",
    "pais_nacionalidad_rep": "México",
    "curp_rep": "XXXX000000XXXXXXXX",
    "rfc_rep": "XXXX000000XXX",
    "tipo_id": "INE - Credencial para votar",
    "num_id": "1234567890",
    "autoridad_emisora": "Instituto Nacional Electoral (INE)",
    "pais_emisor": "México",
    "quien_lleno": "Luis Gomez Montijano",
    "comprobante_tipo": "telefono",
    "poder_tipo": "testimonio",
    "tipo_id_oficial": "ine",
    "firma_razon_social": "EMPRESA, S.A. DE C.V.",
    "firma_rep_legal": "NOMBRE APELLIDO PAT APELLIDO MAT",
}


def texto_pdf(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def test_sujeto_obligado_por_defecto_es_nea():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "pld.pdf")
        generar_pld(dict(DATOS_BASE), out)
        texto = texto_pdf(out)
        check("GRIT PAYMENT SOLUTIONS" in texto,
              "sin sujeto_obligado en los datos, el encabezado sigue siendo Nea/Grit Payment Solutions")
        check("Emisión de Tarjetas de Servicio" in texto,
              "sin sujeto_obligado en los datos, la actividad vulnerable sigue siendo la de Nea")


def test_sujeto_obligado_personalizado_para_grit_mobility():
    datos = dict(DATOS_BASE)
    datos["sujeto_obligado_nombre"] = "GRIT MOBILITY, S.A. DE C.V."
    datos["sujeto_obligado_domicilio"] = "Calle 3 Picos 65, Polanco V Seccion, Miguel Hidalgo, Ciudad de México, México CP 11560"
    datos["actividad_vulnerable"] = "Emisión de tarjetas prepagadas de gasolina"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "pld_grit.pdf")
        generar_pld(datos, out)
        texto = texto_pdf(out)
        check("GRIT MOBILITY, S.A. DE C.V." in texto,
              "con sujeto_obligado_nombre en los datos, el encabezado debe decir Grit Mobility")
        check("Emisión de tarjetas prepagadas de gasolina" in texto,
              "con actividad_vulnerable en los datos, debe imprimirse esa actividad")
        check("GRIT PAYMENT SOLUTIONS" not in texto,
              "el encabezado de Grit Mobility no debe dejar restos del texto de Nea")
        check("Grit Payment Solutions" not in texto,
              "el aviso de privacidad tampoco debe decir Grit Payment Solutions cuando "
              "el sujeto obligado es Grit Mobility")
        check(texto.count("GRIT MOBILITY, S.A. DE C.V.") >= 2,
              "el nombre de Grit Mobility debe aparecer tanto en el encabezado como en "
              "el aviso de privacidad")


DATOS_BASE_PF = {
    "fecha_operacion": "24/03/2026",
    "nombre_completo": "PEREZ GARCIA JUAN",
    "fecha_nacimiento": "07/07/1980",
    "pais_nacimiento": "México",
    "pais_nacionalidad": "México",
    "curp": "PEGJ800707HDFRRN01",
    "rfc": "PEGJ800707ABC",
    "actividad_ocupacion": "Comercio al por menor",
    "calle": "AV. GOBERNADORES",
    "num_ext": "46",
    "colonia": "BURÓCRATAS",
    "cp": "39090",
    "municipio": "CHILPANCINGO DE LOS BRAVO",
    "estado": "GUERRERO",
    "pais_domicilio": "México",
    "telefono": "7471162651",
    "correo": "correo@empresa.mx",
    "tipo_id": "INE - Credencial para votar",
    "num_id": "1234567890",
    "autoridad_emisora": "Instituto Nacional Electoral (INE)",
    "pais_emisor": "México",
    "quien_lleno": "Luis Gomez Montijano",
    "tipo_id_oficial": "ife",
    "comprobante_tipo": "telefono",
}


def test_pld_pf_sujeto_obligado_por_defecto_es_nea():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "pld_pf.pdf")
        generar_pld_pf(dict(DATOS_BASE_PF), out)
        texto = texto_pdf(out)
        check("GRIT PAYMENT SOLUTIONS" in texto,
              "PF: sin sujeto_obligado en los datos, el encabezado sigue siendo Nea/Grit Payment Solutions")
        check("Emisión de Tarjetas de Servicio" in texto,
              "PF: sin sujeto_obligado en los datos, la actividad vulnerable sigue siendo la de Nea")


def test_pld_pf_sujeto_obligado_personalizado_para_grit_mobility():
    datos = dict(DATOS_BASE_PF)
    datos["sujeto_obligado_nombre"] = "GRIT MOBILITY, S.A. DE C.V."
    datos["actividad_vulnerable"] = "Emisión de tarjetas prepagadas de gasolina"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "pld_pf_grit.pdf")
        generar_pld_pf(datos, out)
        texto = texto_pdf(out)
        check("GRIT MOBILITY, S.A. DE C.V." in texto,
              "PF: con sujeto_obligado_nombre en los datos, el encabezado debe decir Grit Mobility")
        check("Emisión de tarjetas prepagadas de gasolina" in texto,
              "PF: con actividad_vulnerable en los datos, debe imprimirse esa actividad")
        check("GRIT PAYMENT SOLUTIONS" not in texto,
              "PF: el encabezado de Grit Mobility no debe dejar restos del texto de Nea")
        check("Grit Payment Solutions" not in texto,
              "PF: el aviso de privacidad tampoco debe decir Grit Payment Solutions cuando "
              "el sujeto obligado es Grit Mobility")
        check(texto.count("GRIT MOBILITY, S.A. DE C.V.") >= 2,
              "PF: el nombre de Grit Mobility debe aparecer tanto en el encabezado como en "
              "el aviso de privacidad")


def _casilla_marcada(path, etiqueta):
    """¿Hay una X dentro de la casilla que sigue a `etiqueta` en su mismo renglón?"""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            palabras = page.extract_words()
            for w in palabras:
                if w["text"] != etiqueta:
                    continue
                for ch in page.chars:
                    if (ch["text"] == "X" and abs(ch["top"] - w["top"]) < 4
                            and w["x1"] < ch["x0"] < w["x1"] + 20):
                        return True
    return False


def test_pld_pm_marca_la_ine_con_la_clave_que_da_el_adaptador():
    import adaptadores
    datos = dict(DATOS_BASE)
    datos["tipo_id_oficial"] = adaptadores._id_oficial("INE - Credencial para votar")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "pld_ine.pdf")
        generar_pld(datos, out)
        check(_casilla_marcada(out, "IFE"),
              "PM: una INE capturada en el expediente marca la casilla IFE del PLD")


def main():
    test_sujeto_obligado_por_defecto_es_nea()
    test_sujeto_obligado_personalizado_para_grit_mobility()
    test_pld_pf_sujeto_obligado_por_defecto_es_nea()
    test_pld_pf_sujeto_obligado_personalizado_para_grit_mobility()
    test_pld_pm_marca_la_ine_con_la_clave_que_da_el_adaptador()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
