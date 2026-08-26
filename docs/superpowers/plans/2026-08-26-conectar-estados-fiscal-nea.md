# Conectar estados de cuenta y fiscal a nea.py — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dos comandos nuevos, `python nea.py estados FOLIO` y `python nea.py fiscal FOLIO`, que llevan documentos de la carpeta canónica de Drive del expediente a las tablas de Supabase que ya lee `insumos_riesgo.py`, para que la compuerta de riesgo (`validador.puede_pasar_a_riesgo`) se pueda abrir sin trabajo manual.

**Architecture:** `bancos.py` (nuevo) es un registro de parsers de banco con un contrato común (`leer`, `cuadra`), hoy con solo `bbva` registrado; expone funciones puras para construir la fila de `estados_cuenta` y una función de persistencia idempotente. `nea.py` gana dos comandos que orquestan: bajar de Drive (`drive_cliente.py`, ya existe), identificar/guardar (`bancos.py`, nuevo), o extraer y proyectar fiscal (`syntage.py` + `info_fiscal.py`, ya existen — solo se conectan).

**Tech Stack:** Python 3.12, pdfplumber (ya usado por `bbva.py`), Supabase (`supabase-py`, cliente en `db.py`), Google Drive API (`drive_cliente.py`).

**Spec:** [docs/superpowers/specs/2026-08-26-conectar-estados-fiscal-nea-design.md](../specs/2026-08-26-conectar-estados-fiscal-nea-design.md)

## Global Constraints

- TDD obligatorio para todo código nuevo (ver `CLAUDE.md`): test primero, verlo fallar, código mínimo, verlo pasar.
- La compuerta del proyecto es `python tests/todas.py`; el veredicto es el código de salida, nunca el texto.
- Nunca crear una entidad de Syntage automáticamente — si el RFC no existe ahí, avisar en rojo y parar (el cliente mete sus propias credenciales del SAT).
- `ceps.py` (Banco del Bajío) y el buró de crédito quedan fuera de este plan (ver spec, sección "Fuera de alcance").
- La tabla `estados_cuenta` de Supabase **ya existe** (`supabase/migracion_02_riesgo.sql`) — no se crea, solo se llena. Su índice único es sobre expresiones (`coalesce(banco,''), coalesce(cuenta,'')`), así que la escritura idempotente se hace por selección-luego-inserta/actualiza en Python, nunca con `upsert(on_conflict=...)` de columnas planas.
- La columna `cuenta` de `estados_cuenta` son los **últimos 4 dígitos**, no el número completo (así lo documenta el propio esquema).

---

## Task 1: `bancos.py` — registro de parsers y construcción de la fila

**Files:**
- Create: `bancos.py`
- Test: `tests/test_bancos.py`

**Interfaces:**
- Consumes: el contrato que ya expone `bbva.py` — `bbva.leer(ruta) -> (encabezado: dict, movimientos: list)`, `bbva.cuadra(encabezado, movimientos) -> (bool, dict)`.
- Produces: `bancos.PARSERS: dict[str, module]`, `bancos.identificar(ruta, parsers=None) -> dict`, `bancos.fila_estados_cuenta(folio: str, encabezado: dict, drive_file_id: str = None) -> dict`. Estas dos funciones las usa el Task 3.

- [ ] **Step 1: Escribir la prueba de `identificar()` — un parser cuadra**

```python
# tests/test_bancos.py
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
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `python tests/test_bancos.py`
Expected: `ModuleNotFoundError: No module named 'bancos'`

- [ ] **Step 3: Escribir `bancos.py` con `PARSERS` e `identificar()` minimos**

```python
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
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `python tests/test_bancos.py`
Expected: las 3 lineas `ok`, sin `FALLA`.

- [ ] **Step 5: Escribir la prueba — ningun parser cuadra, y uno que revienta**

Agregar al final de `tests/test_bancos.py`:

```python
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
```

- [ ] **Step 6: Correr la prueba y verificar que pasa**

Run: `python tests/test_bancos.py`
Expected: todas las lineas `ok`.

- [ ] **Step 7: Escribir la prueba de `fila_estados_cuenta()`**

Agregar a `tests/test_bancos.py`:

```python
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
```

- [ ] **Step 8: Correr la prueba y verificar que falla**

Run: `python tests/test_bancos.py`
Expected: `AttributeError: module 'bancos' has no attribute 'fila_estados_cuenta'`

- [ ] **Step 9: Escribir `fila_estados_cuenta()`**

Agregar a `bancos.py`:

```python
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
```

- [ ] **Step 10: Correr la prueba y verificar que pasa**

Run: `python tests/test_bancos.py`
Expected: todas las lineas `ok`, sin `FALLA`, termina sin traceback.

- [ ] **Step 11: Commit**

```bash
git add bancos.py tests/test_bancos.py
git commit -m "$(cat <<'EOF'
bancos.py: registro de parsers de estado de cuenta, hoy solo BBVA

identificar() prueba cada parser conocido y se queda con el primero que
cuadre; un PDF que no cuadra con ninguno se reporta, nunca se descarta
en silencio. fila_estados_cuenta() arma la fila de Supabase desde un
encabezado, truncando la cuenta a los ultimos 4 digitos como declara
supabase/migracion_02_riesgo.sql.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `bancos.guardar()` — persistencia idempotente en Supabase

**Files:**
- Modify: `bancos.py`

**Interfaces:**
- Consumes: un cliente Supabase `sb` (`db.cliente()`), y una `fila` con la forma que produce `fila_estados_cuenta()` del Task 1.
- Produces: `bancos.guardar(sb, fila) -> str` ("insertada" | "actualizada"). La usa el Task 3.

No lleva prueba automatizada (toca Supabase real): se verifica a mano en el Task 3 contra MEZA-01, igual que el resto de `nea.py` que toca Drive/Supabase (`cmd_drive`, `cmd_riesgo`).

- [ ] **Step 1: Escribir `guardar()`**

Agregar a `bancos.py`:

```python
def guardar(sb, fila):
    """Guarda una fila en `estados_cuenta`, sin duplicar el mismo periodo.

    La tabla tiene un indice unico sobre expresiones
    (coalesce(banco,''), coalesce(cuenta,'')), no sobre columnas planas, asi
    que un upsert(on_conflict=...) de PostgREST no encuentra ese indice como
    arbitro de conflicto. Se busca la fila existente por su llave natural y
    se actualiza o se inserta, en vez de depender de ON CONFLICT.

    Devuelve "insertada" o "actualizada".
    """
    existente = (sb.table("estados_cuenta").select("id")
                 .eq("folio", fila["folio"])
                 .eq("banco", fila["banco"])
                 .eq("cuenta", fila["cuenta"])
                 .eq("fecha_final", fila["fecha_final"])
                 .execute().data)
    if existente:
        sb.table("estados_cuenta").update(fila).eq("id", existente[0]["id"]).execute()
        return "actualizada"
    sb.table("estados_cuenta").insert(fila).execute()
    return "insertada"
```

- [ ] **Step 2: Commit**

```bash
git add bancos.py
git commit -m "$(cat <<'EOF'
bancos.py: guardar() escribe en estados_cuenta sin duplicar periodos

Por seleccion-luego-inserta/actualiza, no por upsert(on_conflict=...):
el indice unico de la tabla es sobre coalesce(banco,''),
coalesce(cuenta,''), no columnas planas, y PostgREST no lo encuentra
como arbitro de conflicto con nombres de columna simples.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `nea.py estados FOLIO`

**Files:**
- Modify: `nea.py` (agregar `cmd_estados`, cablearlo en `main()`)

**Interfaces:**
- Consumes: `bancos.identificar`, `bancos.fila_estados_cuenta`, `bancos.guardar` (Tasks 1-2); `drive_cliente.servicio`, `drive_cliente.documentos_cliente`, `drive_cliente.descargar` (ya existen); `cargar`, `guardar`, `hay_supabase`, `titulo` (ya existen en `nea.py`).
- Produces: comando de CLI `python nea.py estados FOLIO`.

No lleva prueba automatizada propia (orquesta Drive + Supabase reales). Se verifica a mano contra MEZA-01 en el propio Step 3.

- [ ] **Step 1: Agregar `cmd_estados` a `nea.py`**

Insertar despues de `cmd_riesgo` (antes de `def cmd_solicitud`):

```python
def cmd_estados(folio):
    """Baja los estados de cuenta de la carpeta canonica del expediente,
    identifica el banco de cada uno, valida sus totales y guarda lo que
    cuadra en la tabla `estados_cuenta`.

    Un PDF que no cuadra con ningun banco conocido se reporta aparte: nunca
    se descarta en silencio.
    """
    import tempfile

    import bancos
    import drive_cliente

    exp = cargar(folio)
    razon = exp["cliente"]["validado"].get("razon_social") or folio
    titulo("%s — %s" % (razon, folio))

    svc = drive_cliente.servicio()
    # documentos_cliente() ya excluye carpetas; no se filtra por tipo aqui —
    # un comprobante subido como imagen debe intentarse igual y, si ningun
    # parser lo reconoce, aparecer en "no reconocidos", no desaparecer.
    docs = drive_cliente.documentos_cliente(svc, folio)
    if not docs:
        print("  No hay documentos en la carpeta '1 Documentos del cliente'.")
        return 1

    sb = None
    if hay_supabase():
        import db
        sb = db.cliente()
    else:
        print("  AVISO: Supabase no esta configurado. Se identifican los")
        print("  estados de cuenta pero no se guardan.\n")

    rfc_cliente = exp["cliente"]["validado"].get("rfc")
    guardados, no_reconocidos = [], []

    with tempfile.TemporaryDirectory() as tmp:
        for d in docs:
            ruta = os.path.join(tmp, d["name"])
            drive_cliente.descargar(svc, d["id"], ruta)
            resultado = bancos.identificar(ruta)
            if resultado["banco"] is None:
                no_reconocidos.append(d["name"])
                continue
            enc = resultado["encabezado"]
            fila = bancos.fila_estados_cuenta(folio, enc, drive_file_id=d["id"])
            if sb:
                bancos.guardar(sb, fila)
            guardados.append((fila, enc))

    titulo("Resultado")
    print("  Documentos revisados: %d" % len(docs))
    print("  Estados guardados:   %d" % len(guardados))
    if no_reconocidos:
        print("  No reconocidos:")
        for nombre in no_reconocidos:
            print("    · %s (revisar a mano: ¿es un banco sin soporte?)" % nombre)

    if guardados:
        agrupadas = {}
        for fila, enc in guardados:
            clave = (fila["banco"], fila["cuenta"])
            grupo = agrupadas.setdefault(clave, {
                "banco": fila["banco"], "clabe": enc.get("clabe"),
                "titular_es_cliente": (enc.get("rfc") == rfc_cliente)
                                       if enc.get("rfc") else None,
                "periodos": []})
            if fila["fecha_final"]:
                periodo = fila["fecha_final"][:7]
                if periodo not in grupo["periodos"]:
                    grupo["periodos"].append(periodo)
        exp["cuentas_bancarias"] = list(agrupadas.values())
        guardar(exp)

    return 0
```

- [ ] **Step 2: Cablear el comando en `main()`**

En `nea.py`, dentro de `main()`, agregar junto a los demas `if orden ==`:

```python
        if orden == "estados" and len(args) == 1:
            return cmd_estados(args[0])
```

- [ ] **Step 3: Verificar a mano contra MEZA-01**

Run: `python nea.py estados MEZA-01`

Expected: procesa los PDFs de `1 Documentos del cliente` (INE, CSF, comprobante, cotización, autorización de buró, y los 3 estados de cuenta BBVA de mayo/junio/julio); los 3 de BBVA cuadran y se guardan, los demas quedan listados como "no reconocidos" (correcto: no son estados de cuenta). Confirmar despues con:

```bash
python -c "
import sys; sys.path.insert(0, '.')
import db
sb = db.cliente()
print(sb.table('estados_cuenta').select('*').eq('folio', 'MEZA-01').execute().data)
"
```

y que `expedientes/MEZA-01.json` tenga `cuentas_bancarias` con los 3 periodos y `titular_es_cliente: true`.

- [ ] **Step 4: Commit**

```bash
git add nea.py
git commit -m "$(cat <<'EOF'
nea.py estados FOLIO: de la carpeta de Drive a estados_cuenta

Baja los PDFs de '1 Documentos del cliente', identifica el banco de
cada uno con bancos.identificar(), guarda los que cuadran y actualiza
cuentas_bancarias del expediente. Verificado contra MEZA-01: los 3
estados BBVA se reconocen y guardan; el resto de la carpeta se reporta
como no reconocido, sin descartarse en silencio.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `syntage.decidir_fiscal()` — cuándo seguir, cuándo avisar y parar

**Files:**
- Modify: `syntage.py`
- Test: `tests/test_syntage.py`

**Interfaces:**
- Consumes: nada nuevo — es una función pura sobre valores ya definidos por `syntage.buscar_entidad` (entidad: `dict | None`) y `syntage.extraccion_completa` (`(completa: bool, pendientes: list)`).
- Produces: `syntage.decidir_fiscal(entidad, completa, pendientes) -> dict` con clave `"continuar": bool` y `"razon"` cuando `continuar` es `False`. La usa el Task 5.

- [ ] **Step 1: Escribir la prueba**

```python
# tests/test_syntage.py
# -*- coding: utf-8 -*-
"""
Prueba de decidir_fiscal(): la unica logica de syntage.py que no depende de
la red y que decide si 'nea.py fiscal' sigue adelante o avisa y para.

Se corre con:
    python tests/test_syntage.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import syntage

fallas = []


def check(cond, msg):
    print(("  ok  " if cond else "FALLA ") + msg)
    if not cond:
        fallas.append(msg)


print("decidir_fiscal()")

r = syntage.decidir_fiscal(entidad=None, completa=False, pendientes=[])
check(r["continuar"] is False, "sin entidad en Syntage, no continua")
check(r["razon"] == "sin_entidad", "y dice por que: falta el alta del cliente")

r = syntage.decidir_fiscal(entidad={"id": "e1"}, completa=False,
                           pendientes=[{"extractor": "tax-returns", "estado": "running"}])
check(r["continuar"] is False, "con extracciones pendientes, no continua")
check(r["razon"] == "pendiente", "y dice que es porque faltan extracciones")
check(r["pendientes"][0]["extractor"] == "tax-returns", "con el detalle de cuales")

r = syntage.decidir_fiscal(entidad={"id": "e1"}, completa=True, pendientes=[])
check(r["continuar"] is True, "con entidad y extraccion completa, si continua")
check("razon" not in r, "y no hay razon para parar, porque no para")
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `python tests/test_syntage.py`
Expected: `AttributeError: module 'syntage' has no attribute 'decidir_fiscal'`

- [ ] **Step 3: Escribir `decidir_fiscal()`**

Agregar a `syntage.py`, junto a `extraccion_completa`:

```python
def decidir_fiscal(entidad, completa, pendientes):
    """Si 'nea.py fiscal' debe seguir, o avisar y parar — y por que.

    Nunca crea la entidad en Syntage: darse de alta ahi requiere que el
    cliente meta sus propias credenciales del SAT, no es algo que la
    plataforma pueda hacer por el.
    """
    if entidad is None:
        return {"continuar": False, "razon": "sin_entidad"}
    if not completa:
        return {"continuar": False, "razon": "pendiente", "pendientes": pendientes}
    return {"continuar": True}
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `python tests/test_syntage.py`
Expected: todas las lineas `ok`, sin `FALLA`.

- [ ] **Step 5: Commit**

```bash
git add syntage.py tests/test_syntage.py
git commit -m "$(cat <<'EOF'
syntage.py: decidir_fiscal() — nunca crea la entidad, avisa y para

Alta en Syntage requiere que el cliente meta sus propias credenciales
del SAT. Si el RFC no tiene entidad, o si tiene extracciones corriendo,
'nea.py fiscal' debe avisar y parar en vez de usar datos a medias — la
decision queda aislada y probada sin tocar la red.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `nea.py fiscal FOLIO`

**Files:**
- Modify: `nea.py` (agregar `cmd_fiscal`, cablearlo en `main()`)

**Interfaces:**
- Consumes: `syntage.buscar_entidad`, `syntage.extraccion_completa`, `syntage.extraer_todo`, `syntage.guardar_crudo`, `syntage.decidir_fiscal` (Task 4); `info_fiscal.desde_insights`, `info_fiscal.a_supabase` (ya existen); `cargar`, `hay_supabase`, `titulo` (ya existen en `nea.py`).
- Produces: comando de CLI `python nea.py fiscal FOLIO`.

No lleva prueba automatizada propia (orquesta Syntage + Supabase reales). Se verifica a mano contra MEZA-01.

- [ ] **Step 1: Agregar `cmd_fiscal` a `nea.py`**

Insertar despues de `cmd_estados`:

```python
def cmd_fiscal(folio):
    """Extrae balance y estado de resultados de Syntage y los proyecta a
    `info_fiscal`. Nunca da de alta al cliente en Syntage: si no existe ahi,
    avisa en rojo y para — el alta requiere sus propias credenciales del SAT.
    """
    import syntage
    import info_fiscal

    exp = cargar(folio)
    rfc = exp["cliente"]["validado"].get("rfc")
    razon = exp["cliente"]["validado"].get("razon_social") or folio
    titulo("%s — %s" % (razon, folio))

    if not rfc:
        print("  El expediente no tiene RFC validado todavia.")
        return 1

    entidad = syntage.buscar_entidad(rfc)
    completa, pendientes = ((None, [])
                            if entidad is None
                            else syntage.extraccion_completa(rfc))
    decision = syntage.decidir_fiscal(entidad, bool(completa), pendientes)

    if not decision["continuar"]:
        if decision["razon"] == "sin_entidad":
            print("  \033[91m⚠ RFC %s no dado de alta en Syntage.\033[0m" % rfc)
            print("  El cliente debe registrarse ahi con sus propias")
            print("  credenciales del SAT. Pedir a ventas que lo levante.")
        else:
            print("  Extracciones todavia corriendo, no se puede usar a medias:")
            for p in decision["pendientes"]:
                print("    · %s (%s)" % (p.get("extractor"), p.get("estado")))
        return 1

    if not hay_supabase():
        print("  Este comando necesita Supabase: ahi se guarda lo extraido.")
        return 1
    import db
    sb = db.cliente()

    salida, fallos = syntage.extraer_todo(entidad["id"])
    guardadas_crudo = syntage.guardar_crudo(folio, entidad["id"], salida, sb=sb)

    balance = salida.get("metrics/balance-sheet")
    resultados = salida.get("metrics/income-statement")
    filas = info_fiscal.desde_insights(balance, resultados) if (balance or resultados) else []
    guardadas_fiscal = info_fiscal.a_supabase(folio, filas, sb=sb) if filas else 0

    titulo("Resultado")
    print("  Recursos extraidos:      %d" % len(salida))
    print("  Guardados en syntage_datos: %d" % guardadas_crudo)
    print("  Ejercicios en info_fiscal:  %d" % guardadas_fiscal)
    if fallos:
        print("  Recursos que fallaron (no detienen lo demas):")
        for recurso, error in fallos.items():
            print("    · %s: %s" % (recurso, error))

    return 0
```

- [ ] **Step 2: Cablear el comando en `main()`**

```python
        if orden == "fiscal" and len(args) == 1:
            return cmd_fiscal(args[0])
```

- [ ] **Step 3: Verificar a mano contra MEZA-01**

Run: `python nea.py fiscal MEZA-01`

Expected, segun si el RFC `MEHH820721NBA` ya tiene entidad en Syntage:
- Si no existe: el aviso en rojo, y termina con codigo de salida 1.
- Si existe pero hay extracciones corriendo: la lista de pendientes.
- Si esta completa: el resumen de recursos extraidos y guardados.

- [ ] **Step 4: Correr la compuerta completa del proyecto**

Run: `python tests/todas.py`
Expected: `Todo verde.`, codigo de salida 0.

- [ ] **Step 5: Confirmar el efecto sobre la compuerta de riesgo de MEZA-01**

Run: `python nea.py riesgo MEZA-01`

Expected: ya no debe faltar "estados de cuenta procesados" (Task 3) ni "informacion fiscal" (este task) en el mensaje de compuerta cerrada — solo quedaria, si acaso, buro de credito (fuera de alcance de este plan).

- [ ] **Step 6: Commit**

```bash
git add nea.py
git commit -m "$(cat <<'EOF'
nea.py fiscal FOLIO: de Syntage a info_fiscal, sin dar de alta al cliente

Busca la entidad de Syntage por RFC (nunca la crea); si no existe o
tiene extracciones pendientes, avisa y para. Si esta completa, extrae
los insights, los guarda tal cual en syntage_datos y los proyecta a
info_fiscal. Verificado contra MEZA-01 y contra la compuerta completa
del proyecto (tests/todas.py).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
