# -*- coding: utf-8 -*-
"""
Pruebas de drive_cliente.subir_paquete: a Drive solo sube un paquete
verificado, y de él solo los documentos que el verificador revisó.

La compuerta estaba en nea.py subir; `python drive_cliente.py subir` llamaba
a subir_paquete directo y se la saltaba. Y aun con la compuerta, se subía
todo PDF de la carpeta, también los que quedaron de una generación anterior
y que nadie revisó.

Drive se simula: ninguna prueba toca la red. Todos los datos son inventados.

Se corre con:
    python tests/test_subir_paquete.py
"""

import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "generadores"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

import drive_cliente
import fixture_paquete as fx
from generar_paquete import generar_paquete

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


class DriveFalso:
    """Registra lo que se crea; no habla con Google."""

    def __init__(self):
        self.creados = []

    def files(self):
        return self

    def create(self, body, media_body=None, **k):
        self.creados.append(body["name"])
        return self

    def execute(self):
        return {"id": "x", "name": self.creados[-1]}


def _con_drive_falso(fn):
    originales = (drive_cliente.carpeta_expediente, drive_cliente.asegurar_estructura,
                  drive_cliente.hijos)
    drive_cliente.carpeta_expediente = lambda svc, folio: {"id": "exp"}
    drive_cliente.asegurar_estructura = lambda svc, exp_id: {"0": "s", "3": "g"}
    drive_cliente.hijos = lambda svc, carpeta, **k: []
    try:
        return fn()
    finally:
        (drive_cliente.carpeta_expediente, drive_cliente.asegurar_estructura,
         drive_cliente.hijos) = originales


def test_no_sube_un_paquete_sin_verificar():
    exp = fx.persona_moral()
    svc = DriveFalso()
    with tempfile.TemporaryDirectory() as tmp:
        generar_paquete(exp, tmp)
        ruta_man = os.path.join(tmp, "%s_manifiesto.json" % exp["folio"])
        with open(ruta_man, encoding="utf-8") as fh:
            man = json.load(fh)
        del man["verificacion"]
        with open(ruta_man, "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        try:
            _con_drive_falso(lambda: drive_cliente.subir_paquete(svc, exp["folio"], tmp))
            negado = False
        except drive_cliente.PaqueteNoVerificado:
            negado = True
    check(negado and svc.creados == [],
          "subir_paquete se niega con un paquete sin verificar, sin crear nada en Drive (%r)"
          % svc.creados)


def test_solo_sube_lo_que_esta_en_el_manifiesto():
    exp = fx.persona_moral()
    svc = DriveFalso()
    with tempfile.TemporaryDirectory() as tmp:
        man = generar_paquete(exp, tmp)
        for sobrante in ("%s_Contrato_VIEJO.pdf" % exp["folio"],
                         "%s_PARA_FIRMA.pdf" % exp["folio"]):
            with open(os.path.join(tmp, sobrante), "wb") as fh:
                fh.write(b"%PDF-1.4 sobrante")
        _con_drive_falso(lambda: drive_cliente.subir_paquete(svc, exp["folio"], tmp))
    esperados = sorted([d["archivo"] for d in man["documentos"]]
                       + ["%s_manifiesto.json" % exp["folio"]])
    check(sorted(svc.creados) == esperados,
          "solo se suben los documentos verificados y el manifiesto: %r" % svc.creados)


def test_la_linea_de_comandos_tambien_respeta_la_compuerta():
    exp = fx.persona_moral()
    original = drive_cliente.servicio
    drive_cliente.servicio = lambda: DriveFalso()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            generar_paquete(exp, tmp)
            os.remove(os.path.join(tmp, "%s_manifiesto.json" % exp["folio"]))
            r = _con_drive_falso(lambda: drive_cliente.main(
                ["drive_cliente.py", "subir", exp["folio"], tmp]))
    finally:
        drive_cliente.servicio = original
    check(r == 1, "`drive_cliente.py subir` sale con 1 si el paquete no está verificado (%r)" % r)


def main():
    test_no_sube_un_paquete_sin_verificar()
    test_solo_sube_lo_que_esta_en_el_manifiesto()
    test_la_linea_de_comandos_tambien_respeta_la_compuerta()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
