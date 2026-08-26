# -*- coding: utf-8 -*-
"""
bancos.py — Registro de parsers de estado de cuenta, uno por banco
=====================================================================
Cada banco tiene su propio formato de PDF, asi que cada uno vive en su
propio modulo (como ya bbva.py). Este archivo no parsea nada: prueba cada
parser conocido contra un PDF hasta que uno cuadre, y arma la fila que se
guarda en la tabla `estados_cuenta` de Supabase.

**Contrato que debe cumplir un modulo de banco** (el que ya tiene bbva.py):
    leer(ruta) -> (encabezado: dict, movimientos: list)
    cuadra(encabezado, movimientos) -> (bool, diagnostico: dict)

Agregar un banco nuevo es escribir su leer()/cuadra() y anadir una entrada a
PARSERS. No hay que tocar identificar() ni nea.py.
"""

import bbva

PARSERS = {"bbva": bbva}


def identificar(ruta, parsers=None):
    """Prueba cada parser registrado sobre el PDF.

    Devuelve {"banco": nombre, "encabezado":..., "movimientos":...,
    "diagnostico":...} del primero que cuadre. Si ninguno cuadra —o ninguno
    logra ni leer el PDF—, devuelve {"banco": None, "intentos": [...]} con
    el detalle de cada intento: un PDF que no se reconoce se reporta, nunca
    se descarta en silencio.
    """
    parsers = PARSERS if parsers is None else parsers
    intentos = []
    for nombre, modulo in parsers.items():
        try:
            encabezado, movimientos = modulo.leer(ruta)
        except Exception as e:
            intentos.append({"banco": nombre, "error": str(e)})
            continue
        ok, diagnostico = modulo.cuadra(encabezado, movimientos)
        if ok:
            return {"banco": nombre, "encabezado": encabezado,
                    "movimientos": movimientos, "diagnostico": diagnostico}
        intentos.append({"banco": nombre, "cuadra": False, "diagnostico": diagnostico})
    return {"banco": None, "intentos": intentos}


def fila_estados_cuenta(folio, encabezado, drive_file_id=None):
    """La fila que se guarda en `estados_cuenta`, a partir de un encabezado.

    La cuenta se trunca a los ultimos 4 digitos: asi la declara el esquema
    (`supabase/migracion_02_riesgo.sql`) y asi se evita guardar el numero de
    cuenta completo. `titular` y `rfc` del encabezado no son columnas de esta
    tabla — sirven solo para decidir, en nea.py, si la cuenta es del cliente.
    """
    cuenta = encabezado.get("cuenta")
    return {
        "folio": folio,
        "banco": encabezado.get("banco"),
        "cuenta": cuenta[-4:] if cuenta else None,
        "moneda": encabezado.get("moneda"),
        "fecha_inicial": encabezado.get("fecha_inicial"),
        "fecha_final": encabezado.get("fecha_final"),
        "saldo_inicial": encabezado.get("saldo_inicial"),
        "saldo_final": encabezado.get("saldo_final"),
        "saldo_promedio": encabezado.get("saldo_promedio"),
        "numero_depositos": encabezado.get("numero_depositos"),
        "monto_depositos": encabezado.get("monto_depositos"),
        "numero_retiros": encabezado.get("numero_retiros"),
        "monto_retiros": encabezado.get("monto_retiros"),
        "drive_file_id": drive_file_id,
    }


def guardar(sb, fila):
    """Guarda una fila en `estados_cuenta`, sin duplicar el mismo periodo.

    La tabla tiene un indice unico sobre expresiones
    (coalesce(banco,''), coalesce(cuenta,'')), no sobre columnas planas, asi
    que un upsert(on_conflict=...) de PostgREST no encuentra ese indice como
    arbitro de conflicto. Se busca la fila existente por su llave natural y
    se actualiza o se inserta, en vez de depender de ON CONFLICT.

    banco/cuenta pueden venir en None si el encabezado no los pudo leer; el
    cliente de Supabase serializa .eq(col, None) como el texto literal
    "eq.None" (nunca compara con NULL de verdad), asi que esos dos campos se
    filtran con .is_() cuando son None y con .eq() cuando no.

    Devuelve "insertada" o "actualizada".
    """
    def _filtrar(query, columna, valor):
        return query.is_(columna, "null") if valor is None else query.eq(columna, valor)

    q = sb.table("estados_cuenta").select("id").eq("folio", fila["folio"])
    q = _filtrar(q, "banco", fila["banco"])
    q = _filtrar(q, "cuenta", fila["cuenta"])
    q = q.eq("fecha_final", fila["fecha_final"])
    existente = q.execute().data

    if existente:
        sb.table("estados_cuenta").update(fila).eq("id", existente[0]["id"]).execute()
        return "actualizada"
    sb.table("estados_cuenta").insert(fila).execute()
    return "insertada"
