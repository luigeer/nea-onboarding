# -*- coding: utf-8 -*-
"""
Pruebas de los porcentajes del formato de beneficiario controlador.

Con dos decimales fijos, un accionista con una acción de diez millones salía
con "0%" y el mayoritario con "100%": el formato afirmaba que un socio no tenía
nada y que el otro lo tenía todo. Se da la precisión que haga falta para que un
porcentaje que no es cero ni cien no se lea como tal.

Se corre con:
    python tests/test_porcentajes_bc.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generadores"))

import pdfplumber

from generar_beneficiario import _fmt_pct, generar_beneficiario

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def test_porcentajes_comunes_siguen_con_dos_decimales():
    check(_fmt_pct(99.93) == "99.93%", "99.93 se muestra como 99.93%")
    check(_fmt_pct(50) == "50%", "50 se muestra como 50%")
    check(_fmt_pct(100.0) == "100%", "100 exacto se muestra como 100%")
    check(_fmt_pct(0) == "0%", "0 exacto se muestra como 0%")
    check(_fmt_pct(12.345) == "12.35%", "12.345 se redondea a dos decimales")


def test_porcentaje_minimo_no_se_lee_como_cero():
    check(_fmt_pct(68 / 10166000 * 100) == "0.00067%",
          "68 acciones de 10,166,000 no salen como 0%%: %s" % _fmt_pct(68 / 10166000 * 100))
    check(_fmt_pct(1 / 10166000 * 100) == "0.0000098%",
          "1 acción de 10,166,000 no sale como 0%%: %s" % _fmt_pct(1 / 10166000 * 100))


def test_porcentaje_casi_total_no_se_lee_como_cien():
    v = 10165931 / 10166000 * 100
    check(_fmt_pct(v) == "99.99932%", "el mayoritario no sale como 100%%: %s" % _fmt_pct(v))


def test_total_con_ruido_de_flotante_es_cien():
    total = 10165931 / 10166000 * 100 + 68 / 10166000 * 100 + 1 / 10166000 * 100
    check(_fmt_pct(99.99999999999999) == "100%",
          "un total que es 100 salvo ruido de flotante sale como 100%%: %s"
          % _fmt_pct(99.99999999999999))
    check(_fmt_pct(total) == "100%", "la suma de los tres accionistas sale como 100%%: %s"
          % _fmt_pct(total))


def test_tabla_accionaria_muestra_minoritarios():
    datos = {
        "cliente": {"razon_social": "EMPRESA, S.A. DE C.V.", "rfc": "EMP120831AB1"},
        "beneficiarios": [{"nombre": "juan perez garcia", "cargo": "Accionista"}],
        "estructura_accionaria": [
            {"accionista": "Juan Perez Garcia", "acciones": 10165931,
             "importe": 101659310.0, "porcentaje": 10165931 / 10166000 * 100},
            {"accionista": "Ana Lopez Ruiz", "acciones": 69,
             "importe": 690.0, "porcentaje": 69 / 10166000 * 100},
        ],
        "responsable_cumplimiento": {"nombre": "Marcos Siqueiros Ballesteros"},
    }
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "bc.pdf")
        generar_beneficiario(datos, out)
        with pdfplumber.open(out) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
    check("0.00068%" in texto, "la tabla muestra el porcentaje del minoritario")
    check("99.99932%" in texto, "la tabla muestra el porcentaje del mayoritario")
    check("10,166,000" in texto, "la tabla suma las acciones")
    check("10,165,931" in texto, "las acciones de cada renglón llevan separador de miles")


def main():
    test_porcentajes_comunes_siguen_con_dos_decimales()
    test_porcentaje_minimo_no_se_lee_como_cero()
    test_porcentaje_casi_total_no_se_lee_como_cien()
    test_total_con_ruido_de_flotante_es_cien()
    test_tabla_accionaria_muestra_minoritarios()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
