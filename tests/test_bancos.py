# -*- coding: utf-8 -*-
"""
Pruebas del registro de parsers de banco.

`identificar()` no abre PDFs de verdad aqui: se le pasan parsers falsos, del
mismo contrato que bbva.py (leer/cuadra), para probar la logica de "cual
banco es este" sin depender de un archivo real. Esa logica —probar cada
parser conocido, quedarse con el primero que cuadre, nunca descartar en
silencio— es lo que vale la pena de probar.

Se corre con:
    python tests/test_bancos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bancos

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


class ParserFalso(object):
    """Un modulo de banco de mentiras: mismo contrato que bbva.py."""

    def __init__(self, nombre, cuadra_resultado, encabezado=None, revienta=False):
        self.nombre = nombre
        self._cuadra_resultado = cuadra_resultado
        self._encabezado = encabezado or {"banco": nombre.upper()}
        self._revienta = revienta

    def leer(self, ruta):
        if self._revienta:
            raise ValueError("no es un PDF de %s" % self.nombre)
        return self._encabezado, [{"tipo": "abono", "monto": 100.0}]

    def cuadra(self, encabezado, movimientos):
        return self._cuadra_resultado, {"diagnostico": "de prueba"}


print("identificar(): un parser cuadra")
parsers = {
    "bbva": ParserFalso("bbva", cuadra_resultado=True, encabezado={"banco": "BBVA"}),
    "otro": ParserFalso("otro", cuadra_resultado=False),
}
r = bancos.identificar("cualquier-ruta.pdf", parsers=parsers)
check(r["banco"] == "bbva", "identifica el parser que cuadro")
check(r["encabezado"] == {"banco": "BBVA"}, "devuelve el encabezado de ese parser")
check(len(r["movimientos"]) == 1, "y sus movimientos")

print("identificar(): ninguno cuadra")
parsers = {
    "bbva": ParserFalso("bbva", cuadra_resultado=False),
    "otro": ParserFalso("otro", cuadra_resultado=False),
}
r = bancos.identificar("cualquier-ruta.pdf", parsers=parsers)
check(r["banco"] is None, "no identifica ningun banco")
check(len(r["intentos"]) == 2, "pero reporta el intento de cada uno")
check(all("diagnostico" in i for i in r["intentos"]),
      "con el diagnostico de por que no cuadro")

print("identificar(): un parser revienta al leer, no tumba a los demas")
parsers = {
    "bbva": ParserFalso("bbva", cuadra_resultado=True, revienta=True),
    "otro": ParserFalso("otro", cuadra_resultado=True, encabezado={"banco": "OTRO"}),
}
r = bancos.identificar("cualquier-ruta.pdf", parsers=parsers)
check(r["banco"] == "otro",
      "si un parser truena al leer, se prueba el siguiente en vez de fallar todo")

print("fila_estados_cuenta()")
encabezado = {
    "banco": "BBVA", "cuenta": "0481221396", "clabe": "012190004812213963",
    "titular": "HERNAN MEZA HERRERA", "rfc": "MEHH820721NBA", "moneda": "MXN",
    "fecha_inicial": "2026-07-01", "fecha_final": "2026-07-31",
    "saldo_promedio": 124448.24, "saldo_inicial": 130384.62, "saldo_final": 248322.32,
    "numero_depositos": 46, "monto_depositos": 1341308.71,
    "numero_retiros": 152, "monto_retiros": 1223371.01,
}
fila = bancos.fila_estados_cuenta("MEZA-01", encabezado, drive_file_id="abc123")
check(fila["folio"] == "MEZA-01", "trae el folio")
check(fila["banco"] == "BBVA", "trae el banco")
check(fila["cuenta"] == "1396", "la cuenta se trunca a los ultimos 4 digitos")
check(fila["fecha_final"] == "2026-07-31", "trae la fecha de corte")
check(fila["monto_depositos"] == 1341308.71, "trae los montos del encabezado")
check(fila["drive_file_id"] == "abc123", "trae la trazabilidad de Drive")
check("titular" not in fila and "rfc" not in fila,
      "titular y rfc no son columnas de estados_cuenta: no se guardan ahi")

fila_sin_cuenta = bancos.fila_estados_cuenta("MEZA-01", {"banco": "BBVA"})
check(fila_sin_cuenta["cuenta"] is None,
      "sin numero de cuenta en el encabezado, la fila no revienta")
