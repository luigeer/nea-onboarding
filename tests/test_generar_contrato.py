# -*- coding: utf-8 -*-
"""
Pruebas de generar_contrato.py (carátula del contrato de Nea / Grit Payment).

La plantilla trae en el bloque de firma del cliente dos etiquetas: "Nombre:"
arriba y "Apoderado de:" abajo. El nombre es el de la persona que firma; la
empresa va en "Apoderado de:". Invertirlos deja a la sociedad como si fuera
la firmante y a la persona como si fuera la representada.

Se corre con:
    python tests/test_generar_contrato.py
"""

import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "generadores"))

import pdfplumber

from generar_contrato import fill_contrato

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


DATOS = {
    "razon_social": "EMPRESA PRUEBA, S.A. DE C.V.",
    "nombre_comercial": "PRUEBA",
    "rep_legal": "PEREZ GARCIA JUAN",
    "rfc_empresa": "EPR010101AAA",
    "linea_credito": "$25,000.00 M.N.",
    "mensualidad": "$1,050.00 M.N.",
    "firma_razon_social": "EMPRESA PRUEBA, S.A. DE C.V.",
    "firma_rep_legal": "JUAN PEREZ GARCIA",
}


def _top_de(page, texto, x_min=0, x_max=10000):
    for w in page.extract_words():
        if w["text"] == texto and x_min <= w["x0"] <= x_max:
            return w["top"]
    return None


def test_firma_cliente_nombre_arriba_empresa_abajo():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "contrato.pdf")
        fill_contrato(dict(DATOS), out)
        with pdfplumber.open(out) as pdf:
            p = pdf.pages[0]
            # Bloque de firma del cliente: columna izquierda, x < 320.
            nombre = _top_de(p, "Nombre:", x_max=320)
            apoderado = _top_de(p, "Apoderado", x_max=320)
            persona = _top_de(p, "JUAN", 140, 320)
            empresa = _top_de(p, "EMPRESA", 140, 320)
    check(None not in (nombre, apoderado, persona, empresa),
          "el bloque de firma trae las dos etiquetas y los dos datos")
    if None in (nombre, apoderado, persona, empresa):
        return
    # Las etiquetas están a 10 pt una de otra: una tolerancia mayor a ~2 pt ya
    # deja el dato a medio camino y se lee como del renglón vecino.
    check(abs(persona - nombre) < 1.5,
          "el nombre del representante va alineado con 'Nombre:'")
    check(abs(empresa - apoderado) < 1.5,
          "la razón social va alineada con 'Apoderado de:'")


LARGA = "TECNOPROGRAMACION HUMANA ESPECIALIZADA EN SISTEMAS OPERATIVOS, S.A. de C.V."


def test_razon_social_larga_no_se_encima_con_la_firma_de_nea():
    """Con 79 caracteres, ni al tamaño mínimo cabe en un renglón: se salía de la
    columna y se imprimía encima de 'Apoderado de: Grit Payment Solutions'."""
    import verificador
    datos = dict(DATOS, firma_razon_social=LARGA)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "contrato.pdf")
        fill_contrato(datos, out)
        with pdfplumber.open(out) as pdf:
            p = pdf.pages[0]
            apoderado = _top_de(p, "Apoderado", x_max=320)
            suyas = [w for w in p.filter(verificador._es_del_sistema).extract_words()
                     if w["top"] > apoderado - 2 and w["top"] < apoderado + 14
                     and w["x0"] >= 140]
        hallazgos = verificador._regla_firma("contrato", out, datos)
    texto = " ".join(w["text"] for w in suyas)
    check(verificador._aparece(LARGA, verificador._norm(texto)),
          "la razón social larga sale completa (%r)" % texto)
    check(all(w["x1"] <= 320 for w in suyas),
          "no invade la columna de la firma de Nea (x hasta %.0f)"
          % max([w["x1"] for w in suyas] or [0]))
    check(suyas and all(w["top"] - apoderado > -1.5 for w in suyas)
          and abs(min(w["top"] for w in suyas) - apoderado) < 1.5,
          "empieza alineada con 'Apoderado de:'")
    check(hallazgos == [], "el verificador la encuentra (%r)" % hallazgos)


def main():
    test_firma_cliente_nombre_arriba_empresa_abajo()
    test_razon_social_larga_no_se_encima_con_la_firma_de_nea()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
