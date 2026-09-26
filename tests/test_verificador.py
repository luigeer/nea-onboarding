# -*- coding: utf-8 -*-
"""
Pruebas de verificador.py: la revisión de los PDFs ya generados contra el
expediente, antes de subirlos a Drive o mandarlos a firma.

Cada caso reintroduce en un PDF real un error que llegó a un paquete de
cliente (firma invertida, casilla de identificación vacía, sujeto obligado
equivocado, oficial de cumplimiento de la otra empresa) y comprueba que el
verificador lo detecta. El primero comprueba lo contrario: un paquete bien
generado no debe tener hallazgos, o el verificador bloquearía todo.

Todos los datos son inventados.

Se corre con:
    python tests/test_verificador.py
"""

import copy
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "generadores"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixture_paquete as fx
import generar_contrato
import verificador
from adaptadores import ADAPTADORES
from generar_beneficiario import generar_beneficiario
from generar_paquete import generar_paquete
from generar_pld import generar_pld
from generar_pld_pf import generar_pld_pf

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


def reglas(hallazgos):
    return {h["regla"] for h in hallazgos}


def test_un_paquete_bien_generado_no_tiene_hallazgos():
    exp = fx.persona_moral()
    with tempfile.TemporaryDirectory() as tmp:
        manifiesto = generar_paquete(exp, tmp)
        hallazgos = verificador.verificar(exp, tmp, manifiesto)
    check(hallazgos == [],
          "un paquete bien generado no tiene hallazgos (si los tuviera, se bloquea todo): %r"
          % hallazgos)


def test_documento_de_grit_que_nombra_a_grit_payment():
    exp = fx.persona_moral()
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "grit_pld.pdf")
        generar_pld(ADAPTADORES["pld_pm"](exp), ruta)
        h = verificador.verificar_documento("grit_pld_pm", ruta, exp)
    check("empresa" in reglas(h),
          "un PLD de Grit Mobility que nombra a Grit Payment se detecta")


def test_documento_de_nea_que_nombra_a_grit_mobility():
    exp = fx.persona_moral()
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "pld.pdf")
        generar_pld(ADAPTADORES["grit_pld_pm"](exp), ruta)
        h = verificador.verificar_documento("pld_pm", ruta, exp)
    check("empresa" in reglas(h),
          "un PLD de Nea que nombra a Grit Mobility se detecta")


def test_formato_bc_de_nea_con_el_oficial_de_grit():
    exp = fx.persona_moral()
    mal = copy.deepcopy(exp)
    mal["cumplimiento"]["responsable"] = {"nombre": "Luis Gómez Montijano",
                                          "cargo": "Oficial de Cumplimiento"}
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "bc.pdf")
        generar_beneficiario(ADAPTADORES["beneficiario_controlador"](mal), ruta)
        h = verificador.verificar_documento("beneficiario_controlador", ruta, exp)
    check("oficial" in reglas(h),
          "un Formato BC de Nea firmado por el oficial de Grit Mobility se detecta")


def test_contrato_con_la_firma_del_cliente_invertida():
    exp = fx.persona_moral()
    original = copy.deepcopy(generar_contrato.CAMPOS)
    generar_contrato.CAMPOS["firma_razon_social"]["y"] = 141
    generar_contrato.CAMPOS["firma_rep_legal"]["y"] = 131
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "contrato.pdf")
            generar_contrato.fill_contrato(ADAPTADORES["contrato"](exp), ruta)
            h = verificador.verificar_documento("contrato", ruta, exp)
    finally:
        generar_contrato.CAMPOS.clear()
        generar_contrato.CAMPOS.update(original)
    check("firma" in reglas(h),
          "un contrato con la razón social en 'Nombre:' y la persona en 'Apoderado de:' se detecta")


def test_pld_con_otra_casilla_de_identificacion():
    exp = fx.persona_moral()
    datos = ADAPTADORES["pld_pm"](exp)
    datos["tipo_id_oficial"] = "pasaporte"
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "pld.pdf")
        generar_pld(datos, ruta)
        h = verificador.verificar_documento("pld_pm", ruta, exp)
    check("identificacion" in reglas(h),
          "un PLD que marca pasaporte cuando el expediente dice INE se detecta")


def test_pld_sin_ninguna_casilla_de_identificacion():
    exp = fx.persona_moral()
    datos = ADAPTADORES["pld_pm"](exp)
    datos["tipo_id_oficial"] = "sin_casilla"
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "pld.pdf")
        generar_pld(datos, ruta)
        h = verificador.verificar_documento("pld_pm", ruta, exp)
    check("identificacion" in reglas(h),
          "un PLD sin ninguna casilla de identificación marcada se detecta")


def test_lee_las_casillas_del_pld_de_persona_fisica():
    datos = {
        "fecha_operacion": "25/09/2026", "nombre_completo": "PEREZ GARCIA JUAN",
        "fecha_nacimiento": "07/07/1980", "pais_nacimiento": "México",
        "pais_nacionalidad": "México", "curp": "PEGJ800707HDFRRN01",
        "rfc": "PEGJ800707ABC", "actividad_ocupacion": "Comercio",
        "calle": "CALLE", "num_ext": "1", "colonia": "CENTRO", "cp": "01000",
        "municipio": "MUNICIPIO", "estado": "ESTADO", "pais_domicilio": "México",
        "telefono": "5500000000", "correo": "a@b.mx", "tipo_id": "Pasaporte",
        "num_id": "G123", "autoridad_emisora": "SRE", "pais_emisor": "México",
        "quien_lleno": "Persona De Prueba", "tipo_id_oficial": "pasaporte",
        "comprobante_tipo": "telefono",
    }
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "pld_pf.pdf")
        generar_pld_pf(datos, ruta)
        marcadas = verificador.casillas_de_identificacion(ruta)
    check(marcadas == {"pasaporte"},
          "en el PLD de persona física se lee la casilla marcada: %r" % marcadas)


def test_dato_clave_que_no_coincide_con_el_expediente():
    exp = fx.persona_moral()
    datos = ADAPTADORES["contrato"](exp)
    datos["rfc_empresa"] = "XXX000000XX0"
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "contrato.pdf")
        generar_contrato.fill_contrato(datos, ruta)
        h = verificador.verificar_documento("contrato", ruta, exp)
    check("dato" in reglas(h),
          "un contrato con un RFC distinto al del expediente se detecta")


def test_solo_se_sube_o_firma_un_paquete_verificado_sin_hallazgos():
    exp = fx.persona_moral()
    with tempfile.TemporaryDirectory() as tmp:
        generar_paquete(exp, tmp)
        ok, _ = verificador.paquete_listo(tmp, exp["folio"])
        check(ok, "un paquete recién generado y sin hallazgos queda listo")

        ruta_man = os.path.join(tmp, "%s_manifiesto.json" % exp["folio"])
        with open(ruta_man, encoding="utf-8") as fh:
            man = json.load(fh)

        man["verificacion"]["hallazgos"] = [{"regla": "firma", "clave": "contrato",
                                             "archivo": "x.pdf", "detalle": "x"}]
        man["verificacion"]["ok"] = False
        with open(ruta_man, "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        ok, motivos = verificador.paquete_listo(tmp, exp["folio"])
        check(not ok and motivos, "un paquete con hallazgos no queda listo")

        del man["verificacion"]
        with open(ruta_man, "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        ok, motivos = verificador.paquete_listo(tmp, exp["folio"])
        check(not ok and motivos,
              "un paquete que nunca se verificó (generado antes) tampoco queda listo")


def test_subir_y_firma_se_niegan_con_un_paquete_sin_verificar():
    import types
    import nea

    class NoDebeLlamarse(Exception):
        pass

    def prohibido(*a, **k):
        raise NoDebeLlamarse()

    folio = "T-01"
    raiz_original, cargar_original = nea.RAIZ, nea.cargar
    stub = types.ModuleType("drive_cliente")
    stub.servicio = prohibido
    modulos_originales = {m: sys.modules.get(m) for m in ("drive_cliente", "firma")}
    stub_firma = types.ModuleType("firma")
    stub_firma.plan = prohibido
    sys.modules["drive_cliente"] = stub
    sys.modules["firma"] = stub_firma
    try:
        with tempfile.TemporaryDirectory() as tmp:
            paquete = os.path.join(tmp, "expedientes", "%s_paquete" % folio)
            os.makedirs(paquete)
            with open(os.path.join(paquete, "%s_manifiesto.json" % folio), "w",
                      encoding="utf-8") as fh:
                json.dump({"folio": folio, "documentos": []}, fh)
            nea.RAIZ = tmp
            nea.cargar = lambda f: fx.persona_moral()
            try:
                r_subir = nea.cmd_subir(folio)
            except NoDebeLlamarse:
                r_subir = "tocó Drive"
            try:
                r_firma = nea.cmd_firma(folio)
            except NoDebeLlamarse:
                r_firma = "armó la firma"
    finally:
        nea.RAIZ, nea.cargar = raiz_original, cargar_original
        for m, mod in modulos_originales.items():
            if mod is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = mod
    check(r_subir == 1, "subir se niega con un paquete sin verificar, sin tocar Drive (%r)" % r_subir)
    check(r_firma == 1, "firma se niega con un paquete sin verificar (%r)" % r_firma)


def main():
    test_un_paquete_bien_generado_no_tiene_hallazgos()
    test_documento_de_grit_que_nombra_a_grit_payment()
    test_documento_de_nea_que_nombra_a_grit_mobility()
    test_formato_bc_de_nea_con_el_oficial_de_grit()
    test_contrato_con_la_firma_del_cliente_invertida()
    test_pld_con_otra_casilla_de_identificacion()
    test_pld_sin_ninguna_casilla_de_identificacion()
    test_lee_las_casillas_del_pld_de_persona_fisica()
    test_dato_clave_que_no_coincide_con_el_expediente()
    test_solo_se_sube_o_firma_un_paquete_verificado_sin_hallazgos()
    test_subir_y_firma_se_niegan_con_un_paquete_sin_verificar()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
