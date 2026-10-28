# -*- coding: utf-8 -*-
"""
Pruebas de la subida de documentos del cliente a '1 Documentos del cliente'
y del aviso de `nea.py estado` cuando el expediente y Drive no cuadran.

Hasta ahora esa copia se hacía a mano, y CIL-01 se quedó sin los documentos
de la empresa en Drive aunque el expediente ya los tenía registrados. Nadie
se enteró porque nada comparaba una cosa con la otra.

Drive se simula: ninguna prueba toca la red. Todos los datos son inventados.

Se corre con:
    python tests/test_documentos_cliente_drive.py
"""

import contextlib
import io
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import drive_cliente
import nea

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


class DriveFalso:
    """Registra lo que se crea en la carpeta 1; no habla con Google."""

    def __init__(self, existentes=()):
        self.carpeta_1 = [{"id": "e%d" % i, "name": n, "mimeType": "application/pdf"}
                          for i, n in enumerate(existentes)]
        self.creados = []
        self.otras_llamadas = []

    def files(self):
        return self

    def create(self, body, media_body=None, **k):
        # No se guarda media_body: retiene el archivo abierto y Windows no
        # deja limpiar la carpeta temporal.
        self.creados.append({"name": body["name"], "parents": body.get("parents")})
        self._ultimo = {"id": "nuevo", "name": body["name"]}
        return self

    def update(self, **k):
        self.otras_llamadas.append(("update", k))
        return self

    def delete(self, **k):
        self.otras_llamadas.append(("delete", k))
        return self

    def execute(self):
        return self._ultimo


@contextlib.contextmanager
def drive_falso(svc):
    originales = (drive_cliente.carpeta_expediente, drive_cliente.asegurar_estructura,
                  drive_cliente.hijos, drive_cliente.servicio)
    drive_cliente.carpeta_expediente = lambda s, folio: {"id": "exp"}
    drive_cliente.asegurar_estructura = lambda s, exp_id, avisos=None: {
        "0": "superados", "1": "cliente", "2": "analisis", "3": "generados", "4": "firmados"}
    drive_cliente.hijos = lambda s, carpeta, **k: list(svc.carpeta_1) if carpeta == "cliente" else []
    drive_cliente.servicio = lambda: svc
    try:
        yield
    finally:
        (drive_cliente.carpeta_expediente, drive_cliente.asegurar_estructura,
         drive_cliente.hijos, drive_cliente.servicio) = originales


def _pdf(tmp, nombre="acta de ventas.pdf"):
    ruta = os.path.join(tmp, nombre)
    with open(ruta, "wb") as fh:
        fh.write(b"%PDF-1.4 inventado")
    return ruta


# ─────────────────────────────────────────────────────────────────────────────
# Subida
# ─────────────────────────────────────────────────────────────────────────────
def test_sube_con_el_nombre_canonico_a_la_carpeta_1():
    svc = DriveFalso()
    with tempfile.TemporaryDirectory() as tmp, drive_falso(svc):
        ruta = _pdf(tmp)
        f, subido = drive_cliente.subir_documento_cliente(
            svc, "PRUEBA-01", ruta, "acta_constitutiva", "La Prueba, S.A. de C.V.",
            "2001-08-23")
    esperado = "ActaConstitutiva_LaPrueba_firmada-2001-08-23.pdf"
    check(subido and [c["name"] for c in svc.creados] == [esperado]
          and svc.creados[0]["parents"] == ["cliente"],
          "sube a '1 Documentos del cliente' con el nombre de nomenclatura (%r)"
          % svc.creados)
    check(f.get("name") == esperado, "devuelve el archivo creado (%r)" % f)


def test_no_sube_de_nuevo_si_ya_existe_el_nombre():
    nombre = "CSF_LaPrueba_emitida-2026-09-01.pdf"
    svc = DriveFalso(existentes=[nombre])
    with tempfile.TemporaryDirectory() as tmp, drive_falso(svc):
        ruta = _pdf(tmp, "csf.pdf")
        f, subido = drive_cliente.subir_documento_cliente(
            svc, "PRUEBA-01", ruta, "csf", "La Prueba", "2026-09-01")
    check(not subido and svc.creados == [] and svc.otras_llamadas == [],
          "si ya existe el mismo nombre no sube nada ni toca lo que hay (%r, %r)"
          % (svc.creados, svc.otras_llamadas))
    check(f.get("name") == nombre, "devuelve el archivo que ya estaba (%r)" % f)


def test_el_original_se_queda_donde_estaba():
    svc = DriveFalso()
    with tempfile.TemporaryDirectory() as tmp, drive_falso(svc):
        ruta = _pdf(tmp)
        drive_cliente.subir_documento_cliente(
            svc, "PRUEBA-01", ruta, "poder", "La Prueba", "2020-01-01")
        sigue = os.path.exists(ruta)
        with open(ruta, "rb") as fh:
            intacto = fh.read() == b"%PDF-1.4 inventado"
        en_la_carpeta = sorted(os.listdir(tmp))
    check(sigue and intacto and en_la_carpeta == ["acta de ventas.pdf"],
          "el archivo local no se mueve, no se renombra y no se borra (%r)" % en_la_carpeta)
    check(svc.otras_llamadas == [], "en Drive solo se crea, nunca se mueve ni borra")


def test_conserva_la_extension_del_original():
    svc = DriveFalso()
    with tempfile.TemporaryDirectory() as tmp, drive_falso(svc):
        ruta = _pdf(tmp, "ine frente.JPG")
        drive_cliente.subir_documento_cliente(
            svc, "PRUEBA-01", ruta, "identificacion", "Ana Prueba", "2033-12-31")
    check([c["name"] for c in svc.creados] == ["INE_AnaPrueba_vence-2033-12-31.jpg"],
          "una foto conserva su extensión (%r)" % svc.creados)


def test_tipo_desconocido_no_sube_nada():
    svc = DriveFalso()
    with tempfile.TemporaryDirectory() as tmp, drive_falso(svc):
        ruta = _pdf(tmp)
        try:
            drive_cliente.subir_documento_cliente(
                svc, "PRUEBA-01", ruta, "acta_rara", "La Prueba", "2020-01-01")
            negado = False
        except ValueError:
            negado = True
    check(negado and svc.creados == [], "un tipo desconocido se rechaza sin subir nada")


def test_linea_de_comandos_de_drive_cliente():
    svc = DriveFalso()
    with tempfile.TemporaryDirectory() as tmp, drive_falso(svc):
        ruta = _pdf(tmp)
        r = drive_cliente.main(["drive_cliente.py", "cliente", "PRUEBA-01", ruta,
                                "acta_constitutiva", "La Prueba", "2001-08-23"])
    check(r == 0 and len(svc.creados) == 1,
          "`drive_cliente.py cliente` sube el documento (%r, %r)" % (r, svc.creados))


def test_linea_de_comandos_de_nea():
    svc = DriveFalso(existentes=["ActaConstitutiva_LaPrueba_firmada-2001-08-23.pdf"])
    salida = io.StringIO()
    with tempfile.TemporaryDirectory() as tmp, drive_falso(svc), \
            contextlib.redirect_stdout(salida):
        ruta = _pdf(tmp)
        r = nea.main(["nea.py", "documento", "PRUEBA-01", ruta,
                      "acta_constitutiva", "La Prueba", "2001-08-23"])
    check(r == 0 and svc.creados == [] and "ya estaba" in salida.getvalue().lower(),
          "`nea.py documento` avisa que ya estaba y no lo duplica (%r)" % salida.getvalue())


# ─────────────────────────────────────────────────────────────────────────────
# Aviso en `nea.py estado`
# ─────────────────────────────────────────────────────────────────────────────
def _exp(documentos):
    from schema_expediente import expediente_vacio
    exp = expediente_vacio()
    exp["folio"] = "PRUEBA-01"
    exp["cliente"]["validado"]["razon_social"] = "LA PRUEBA"
    exp["documentos"] = documentos
    return exp


def _estado(exp, svc):
    original = nea.cargar
    nea.cargar = lambda folio: exp
    salida = io.StringIO()
    try:
        with drive_falso(svc), contextlib.redirect_stdout(salida):
            r = nea.cmd_estado("PRUEBA-01")
    finally:
        nea.cargar = original
    return r, salida.getvalue()


def test_estado_avisa_si_faltan_documentos_en_drive():
    docs = [{"tipo": "csf_cliente"}, {"tipo": "acta_constitutiva"},
            {"tipo": "poder"}, {"tipo": "csf_cliente", "superado_por": "otro"}]
    svc = DriveFalso(existentes=["CSF_LaPrueba_emitida-2026-09-01.pdf"])
    r, texto = _estado(_exp(docs), svc)
    check(r == 0 and "3 documento" in texto and "1 archivo" in texto,
          "estado avisa: 3 vigentes en el expediente, 1 archivo en Drive (%r)"
          % texto[-400:])


def test_estado_no_avisa_si_cuadra():
    docs = [{"tipo": "csf_cliente"}, {"tipo": "acta_constitutiva", "superado_por": "x"}]
    svc = DriveFalso(existentes=["CSF_LaPrueba_emitida-2026-09-01.pdf"])
    r, texto = _estado(_exp(docs), svc)
    check(r == 0 and "Drive" not in texto,
          "estado no dice nada de Drive cuando cuadra (%r)" % texto[-400:])


def test_estado_sigue_si_drive_no_responde():
    def sin_drive():
        raise SystemExit("Falta cliente_oauth.json")
    original_cargar, original_servicio = nea.cargar, drive_cliente.servicio
    nea.cargar = lambda folio: _exp([{"tipo": "csf_cliente"}])
    drive_cliente.servicio = sin_drive
    salida = io.StringIO()
    try:
        with contextlib.redirect_stdout(salida):
            r = nea.cmd_estado("PRUEBA-01")
    finally:
        nea.cargar, drive_cliente.servicio = original_cargar, original_servicio
    check(r == 0 and "no se pudo revisar drive" in salida.getvalue().lower(),
          "sin Drive, estado lo dice y termina normal (%r)" % salida.getvalue()[-300:])


def main():
    test_sube_con_el_nombre_canonico_a_la_carpeta_1()
    test_no_sube_de_nuevo_si_ya_existe_el_nombre()
    test_el_original_se_queda_donde_estaba()
    test_conserva_la_extension_del_original()
    test_tipo_desconocido_no_sube_nada()
    test_linea_de_comandos_de_drive_cliente()
    test_linea_de_comandos_de_nea()
    test_estado_avisa_si_faltan_documentos_en_drive()
    test_estado_no_avisa_si_cuadra()
    test_estado_sigue_si_drive_no_responde()
    print()
    if fallas:
        print("%d falla(s)" % len(fallas))
        return 1
    print("Todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
