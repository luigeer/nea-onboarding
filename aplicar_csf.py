# -*- coding: utf-8 -*-
"""
aplicar_csf.py — Aplica una CSF a un expediente según el sujeto
================================================================
El mismo extractor determinista sirve para tres sujetos distintos; lo que
cambia es a qué parte del expediente se vuelca:

  cliente       la persona moral o física que contrata (etapa 0)
  obligado      el obligado solidario (sus datos, no el flag: eso es de riesgo)
  beneficiario  un beneficiario controlador; se funde con el ya listado si existe

Uso:
    python aplicar_csf.py <csf.pdf> <expediente.json> <cliente|obligado|beneficiario>

El expediente se modifica en su lugar. Si el archivo no existe y el sujeto es
'cliente', se crea desde la plantilla vacía.
"""

import json
import sys

from schema_expediente import expediente_vacio
from extraer_csf import extraer_csf, a_expediente, a_obligado_solidario, a_beneficiario


def main(ruta_pdf, ruta_exp, sujeto):
    try:
        with open(ruta_exp, encoding="utf-8") as fh:
            exp = json.load(fh)
        creado = False
    except FileNotFoundError:
        if sujeto != "cliente":
            print("El expediente %s no existe. El primer documento de un expediente "
                  "es la CSF del cliente, no la del %s." % (ruta_exp, sujeto))
            return 1
        exp = expediente_vacio()
        creado = True

    csf = extraer_csf(ruta_pdf)

    if sujeto == "cliente":
        a_expediente(csf, exp)
        puestos = ["cliente.validado.*", "tipo_cliente"]
    elif sujeto == "obligado":
        puestos = a_obligado_solidario(csf, exp)
    elif sujeto == "beneficiario":
        puestos, nuevo = a_beneficiario(csf, exp)
        if nuevo:
            print("Beneficiario nuevo: %s. Falta su participación, que sale de la "
                  "constitutiva." % csf["razon_social"])
        else:
            print("Beneficiario ya listado: %s. Se completaron sus campos vacíos."
                  % csf["razon_social"])
    else:
        print(__doc__)
        return 1

    with open(ruta_exp, "w", encoding="utf-8") as fh:
        json.dump(exp, fh, ensure_ascii=False, indent=2)

    print("%s: %s (%s)" % ("Expediente creado" if creado else "Expediente actualizado",
                           ruta_exp, csf["razon_social"]))
    if puestos:
        print("Campos llenados: %s" % ", ".join(puestos))
    else:
        print("Ningún campo vacío que llenar: todo lo que trae la CSF ya estaba validado.")
    for a in csf.get("alertas", []):
        print("AVISO: %s" % a)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[3] not in ("cliente", "obligado", "beneficiario"):
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
