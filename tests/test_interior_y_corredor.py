# -*- coding: utf-8 -*-
"""
Dos defectos que reportó un cliente al firmar (NUBA-01):

1. El número interior del domicilio fiscal no llegaba al Formato PLD. La CSF lo
   trae ("CUARTO PISO L-409"), pero al abrir el expediente solo se copiaba el
   número exterior, así que el PLD decía "630" a secas.

2. El Formato de Beneficiario Controlador solo sabía decir "Escritura Pública" y
   "Notario Público". Hay sociedades constituidas por póliza ante corredor
   público, y para ellas el formato debe decir "Póliza" y "Corredor Público".

Todos los datos son inventados.

Se corre con:
    python tests/test_interior_y_corredor.py
"""

import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "generadores"))

import pdfplumber

from adaptadores import ADAPTADORES
from extraer_csf import a_expediente
from generar_beneficiario import generar_beneficiario
from schema_expediente import expediente_vacio

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def csf_con_interior():
    return {
        "rfc": "EJE180101AB1", "tipo_cliente": "persona_moral",
        "razon_social": "EJEMPLO, S.A. de C.V.", "fecha_emision": "2026-09-01",
        "domicilio": {"calle": "CALLE AVENA", "num_ext": "630",
                      "num_int": "CUARTO PISO L-409", "colonia": "GRANJAS MEXICO",
                      "cp": "08400", "municipio": "IZTACALCO",
                      "estado": "CIUDAD DE MEXICO", "pais": "México"},
        "alertas": [],
    }


def expediente_pm():
    e = expediente_vacio()
    e["folio"] = "T-01"
    e["tipo_cliente"] = "persona_moral"
    e["cliente"]["validado"]["razon_social"] = "EJEMPLO, S.A. de C.V."
    e["representante_legal"]["validado"]["nombre"] = "JUAN PEREZ GARCIA"
    e["beneficiarios_controladores"] = [{"nombre": "JUAN PEREZ GARCIA"}]
    return e


def texto_pdf(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def texto_bc(exp):
    datos = ADAPTADORES["beneficiario_controlador"](exp)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "bc.pdf")
        generar_beneficiario(datos, out)
        return texto_pdf(out)


def test_el_expediente_conserva_el_numero_interior_de_la_csf():
    e = expediente_vacio()
    a_expediente(csf_con_interior(), e)
    check(e["cliente"]["validado"]["domicilio"].get("num_int") == "CUARTO PISO L-409",
          "al abrir el expediente, el domicilio guarda el número interior de la CSF")


def test_el_pld_pm_lleva_exterior_e_interior():
    e = expediente_pm()
    e["cliente"]["validado"]["domicilio"] = dict(csf_con_interior()["domicilio"])
    d = ADAPTADORES["pld_pm"](e)
    check(d["num_ext"] == "630 INT. CUARTO PISO L-409",
          "el PLD de persona moral pone exterior e interior en 'No. Exterior/Interior' "
          "(salió %r)" % d["num_ext"])


def test_el_pld_pf_lleva_exterior_e_interior():
    e = expediente_vacio()
    e["tipo_cliente"] = "pfae"
    e["representante_legal"]["validado"]["nombre"] = "JUAN PEREZ GARCIA"
    e["cliente"]["validado"]["domicilio"] = dict(csf_con_interior()["domicilio"])
    for clave in ("pld_pf", "grit_pld_pf"):
        d = ADAPTADORES[clave](e)
        check(d["num_ext"] == "630 INT. CUARTO PISO L-409",
              "%s pone exterior e interior (salió %r)" % (clave, d["num_ext"]))


def test_el_pld_pf_no_saca_el_interior_largo_de_la_hoja():
    """Caso real (SIQUEIROS-01): '100 INT. PARQUE REFORMA D1601' se salía del
    margen derecho y el último dígito quedaba fuera del papel."""
    from generar_pld_pf import generar_pld_pf, MR
    e = expediente_vacio()
    e["tipo_cliente"] = "pfae"
    e["fechas"]["operacion"] = "2026-10-14"
    e["cliente"]["validado"].update({
        "rfc": "PEPJ800101AB1", "actividad_economica": "Consultoría",
        "telefono": "55 1234 5678", "correo": "juan@ejemplo.com",
        "domicilio": {"calle": "AVENIDA (AV.) AV DE LOS POETAS", "num_ext": "100",
                      "num_int": "PARQUE REFORMA D1601", "colonia": "SAN MATEO",
                      "cp": "05600", "municipio": "CUAJIMALPA DE MORELOS",
                      "estado": "CIUDAD DE MEXICO", "pais": "México"}})
    e["representante_legal"]["validado"].update({
        "nombre": "JUAN PEREZ GARCIA", "curp": "PEPJ800101HDFRRN09",
        "rfc": "PEPJ800101AB1", "fecha_nacimiento": "1980-01-01",
        "pais_nacimiento": "México", "pais_nacionalidad": "México",
        "identificacion": {"tipo": "INE", "numero": "123", "autoridad_emisora": "INE",
                           "pais_emisor": "México"}})
    e["quien_lleno"] = "Prueba"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "pld.pdf")
        generar_pld_pf(ADAPTADORES["grit_pld_pf"](e), out)
        with pdfplumber.open(out) as pdf:
            pag = pdf.pages[0]
            texto = pag.extract_text() or ""
            etiqueta = next(w for w in pag.extract_words()
                            if w["text"].startswith("Exterior/Interior"))
            renglon = [ch for ch in pag.chars if abs(ch["top"] - etiqueta["top"]) < 2]
            ancho = pag.width
    check("PARQUE REFORMA D1601" in texto, "el interior completo aparece en el PLD")
    check(max(ch["x1"] for ch in renglon) <= MR + 1,
          "el número exterior/interior no rebasa el margen derecho (llega a %.0f, "
          "margen %d, hoja %.0f)" % (max(ch["x1"] for ch in renglon), MR, ancho))


def test_el_pld_sin_interior_queda_igual():
    e = expediente_pm()
    dom = dict(csf_con_interior()["domicilio"])
    dom.pop("num_int")
    e["cliente"]["validado"]["domicilio"] = dom
    d = ADAPTADORES["pld_pm"](e)
    check(d["num_ext"] == "630", "sin interior, el PLD lleva solo el exterior")


def test_el_bc_de_constitucion_notarial_dice_escritura_y_notario():
    e = expediente_pm()
    e["constitucion"].update({"instrumento": "12,345", "fecha": "2018-10-04",
                              "fedatario": "Lic. Ana Gómez", "notaria": "10",
                              "plaza": "Ciudad de México"})
    t = texto_bc(e)
    check("Escritura Pública No. 12,345" in t, "notarial: dice 'Escritura Pública No.'")
    check("Notario Público No. 10" in t, "notarial: dice 'Notario Público No.'")


def test_el_bc_de_constitucion_por_corredor_dice_poliza_y_corredor():
    e = expediente_pm()
    e["constitucion"].update({"instrumento": "3,507", "fecha": "2018-10-04",
                              "fedatario": "Lic. Ramón Pérez", "notaria": "1",
                              "plaza": "Ciudad de México",
                              "tipo_fedatario": "corredor"})
    t = texto_bc(e)
    check("Póliza No. 3,507" in t, "corredor: dice 'Póliza No.'")
    check("Corredor Público No. 1" in t, "corredor: dice 'Corredor Público No.'")
    check("Escritura Pública" not in t and "Notario Público" not in t,
          "corredor: no quedan restos de 'Escritura' ni 'Notario'")


def main():
    test_el_expediente_conserva_el_numero_interior_de_la_csf()
    test_el_pld_pm_lleva_exterior_e_interior()
    test_el_pld_pf_lleva_exterior_e_interior()
    test_el_pld_pf_no_saca_el_interior_largo_de_la_hoja()
    test_el_pld_sin_interior_queda_igual()
    test_el_bc_de_constitucion_notarial_dice_escritura_y_notario()
    test_el_bc_de_constitucion_por_corredor_dice_poliza_y_corredor()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
