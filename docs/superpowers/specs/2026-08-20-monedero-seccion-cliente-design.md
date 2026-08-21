# Monedero como sección del cliente — diseño

## Por qué

`estaciones_monedero.py` y `estado_cuenta_monedero.py` ya existen y funcionan
por CLI (`python estaciones_monedero.py plan`, `python estado_cuenta_monedero.py
reporte <carpeta>`), pero viven fuera del flujo de onboarding: hay que saber
que existen y correrlos a mano. Este trabajo los convierte en una sección más
del expediente del cliente en el front (`front.py`), junto a Score, Perfil,
Documentos, etc.

El propósito de negocio no es solo "¿usa monedero?" — son tres preguntas que
juntas deciden si vale la pena perseguir el desplazamiento:

1. **Adopción y consumo** — ¿ya usa un monedero de combustible, y cuánto
   factura al mes? Nea entra a ese mercado; un cliente que no usa monedero no
   es el caso de uso.
2. **Concentración de estaciones** — ¿en cuántas estaciones distintas carga?
   El producto de Nea es *closed loop*: importa saber en cuántas estaciones
   hay que tener cobertura, no solo cuánto se gasta.
3. **Comisión actual** — ¿cuánto le cobra el monedero de hoy? Mientras más le
   cobren, mayor la oportunidad de desplazarlos. La referencia de negocio es
   **1.75%**: por encima de eso, es un cliente atractivo para migrar.

El **mejor caso** es un cliente que carga millones de pesos al mes, en pocas
estaciones, con un monedero que le cobra bastante más de 1.75%.

## Qué se confirmó con datos reales (spike)

Contra un cliente con relación confirmada de Efecticard, las facturas de
Syntage (`syntage.facturas`) traen, además del CFDI de $1 que ya se usaba para
confirmar el patrón, un concepto separado **"Cargo Administrativo"** con
monto real cuando el monedero cobra su comisión. En los periodos donde esa
factura viene junto con un concepto `DISPERSION` (la carga de saldo a la
tarjeta), la relación es exacta:

| Dispersión | Cargo Administrativo | % |
|---|---|---|
| $10,000 | $300 | 3.0% |
| $15,000 | $450 | 3.0% |
| $40,000 | $1,200 | 3.0% |
| $50,000 | $1,500 | 3.0% |
| $25,000 | $750 | 3.0% |
| $20,000 | $600 | 3.0% |

Esto confirma que **la comisión se puede leer directo de la API de Syntage,
sin descargar ni parsear ningún PDF/XML** — es una factura más, no algo
escondido en el complemento.

## Alcance

- Se dispara **por cliente, a demanda**, solo durante onboarding activo — no
  es un barrido periódico sobre toda la cartera ni un monitoreo continuo de
  clientes ya cerrados.
- Es **informativo, nunca bloquea**: el expediente avanza de etapa
  independientemente de si este análisis se corrió o de lo que haya
  encontrado.
- Cubre la ventana de los **últimos 3 meses** (misma ventana que
  `confirmar_monedero_real`), para que la confirmación del monedero, el plan
  de descarga y la comisión hablen del mismo periodo.
- Si el cliente usa más de un monedero real a la vez, se muestran todos —
  no solo el primero que se detecta.

## Arquitectura

Dos módulos existentes, sin proceso nuevo ni tabla nueva en Supabase.
`front.py` los importa y llama directo, igual que ya hace con
`resumen_ejecutivo` en `_tab_resumen`.

### `estaciones_monedero.py` — Etapa 1 (API, sin descargar nada)

Función nueva:

```python
def comision_candidatas(entidad_id, rfc_monedero):
    """Conceptos de 'Cargo Administrativo' con monto real: la comisión que
    cobra el monedero, aparte del CFDI de $1 que solo confirma el patron."""
    candidatas = []
    for f in syntage.facturas(entidad_id, rfc_monedero):
        for item in f.get("items") or []:
            desc = (item.get("description") or "").strip().lower()
            monto = item.get("totalAmount")
            if desc == "cargo administrativo" and (monto or 0) >= UMBRAL_MONTO_SIMBOLICO:
                candidatas.append({"mes": (f.get("issuedAt") or "")[:7],
                                    "folio_fiscal": f.get("uuid"),
                                    "monto": monto, "fecha": f.get("issuedAt")})
    return candidatas
```

Y una función de orquestación por cliente (nueva, reemplaza a `plan_descarga`
como punto de entrada del front — `plan_descarga` sigue existiendo para el
CLI/barrido de Etapa 1 original):

```python
def revisar_cliente(folio):
    """Todo lo que Etapa 1 puede decir de un cliente sin descargar nada:
    monedero(s) real(es) confirmado(s), plan de que bajar a mano, y la
    comision ya calculable via API. Escribe out/{folio}_monedero.json."""
```

`revisar_cliente` resuelve el RFC/entidad del folio (mismo patrón que
`monederos.analizar_cliente`), corre `detectar_monederos` para encontrar
candidatos del padrón, y para cada uno `facturas_candidatas` +
`confirmar_monedero_real` + (si es real) `comision_candidatas`. Escribe el
resultado a `out/{folio}_monedero.json` (ver forma abajo) y lo regresa.

### `estado_cuenta_monedero.py` — Etapa 2 (parser de lo ya descargado)

Función nueva, delgada sobre lo que ya existe:

```python
def reporte_cliente(rfc_cliente, carpeta="descargas/monederos"):
    """reporte_carpeta() filtrado a un solo cliente — lee los PDF/XML que ya
    calzan la convencion de nombre para este RFC, agrega por mes y por
    estacion. No decide nada de comision: eso ya lo tiene Etapa 1."""
```

El front la llama, cruza el `total` de cada mes contra la `comision` que ya
traía el JSON de Etapa 1, calcula el % por mes, y reescribe
`out/{folio}_monedero.json` con la sección `reporte` llena.

## Por qué el front escribe a disco aquí (y en ningún otro tab)

Hoy `front.py` nunca persiste nada: `_tab_resumen` calcula y muestra en vivo,
y solo el CLI (`python nea.py resumen <folio>`) escribe a `out/`. Este tab
rompe ese patrón a propósito, no por descuido: la descarga manual entre
Etapa 1 y Etapa 2 puede tardar días, y Etapa 2 necesita saber qué plan (qué
mes, qué folio fiscal, qué comisión) generó Etapa 1 para poder cruzarlo —
`st.session_state` no sobrevive a que el operador cierre el navegador y
vuelva después. Por eso los botones del tab sí escriben
`out/{folio}_monedero.json`, a diferencia del resto del front.

## Forma de `out/{folio}_monedero.json`

```json
{
  "generado_etapa1": "2026-08-20T22:30:00",
  "generado_etapa2": null,
  "monederos": [
    {
      "rfc_monedero": "EFE8908015L3",
      "nombre_comercial": "Efecticard",
      "es_real": true,
      "plan_descarga": [
        {"mes": "2026-06", "folio_fiscal": "...",
         "archivo_esperado": "RFC_CLIENTE_EFE8908015L3_2026-06.pdf"}
      ],
      "comision": {"2026-06": {"monto": 900.0, "folio_fiscal": "..."}},
      "reporte": null,
      "sospechosos": []
    }
  ]
}
```

Si `detectar_monederos` no encuentra ningún candidato del padrón,
`"monederos"` es `[]` y el tab lo reporta como "no se detectó monedero" sin
tronar. Un candidato que no confirma el patrón (`es_real: false`) se guarda
igual, para distinguir "no usa monedero" de "usa una gasolinera-que-también-
es-monedero pero fue compra directa".

## El tab en `front.py`

Nueva función `_tab_monedero(folio)`, agregada a `vista_cliente` junto a las
demás. Lee `out/{folio}_monedero.json` si existe; si no, explica qué hacen
los dos botones y no muestra nada más.

| Situación | Qué ve el operador |
|---|---|
| Archivo no existe | Explicación + botón "Revisar monedero" |
| Etapa 1 corrida, ningún monedero confirmado | Aviso informativo, sin bloquear |
| Etapa 1 corrida, 1+ confirmado(s) | Comisión en pesos, tabla de qué descargar, botón "Leer descargas" |
| Etapa 2 corrida | + total facturado, % de comisión, estaciones — por mes y agregado |
| Mes con comisión pero sin complemento subido | Comisión en pesos se muestra; el % de ese mes dice "falta subir el complemento" |
| PDF/XML que no cuadró | Se lista aparte como sospechoso, nunca entra al agregado |

Ambos botones quedan siempre visibles y disponibles para volver a correr, no
solo la primera vez. Si hay más de un monedero real, cada uno es su propio
bloque dentro del tab.

## Manejo de errores

Mismo patrón que el resto del sistema — nunca tronar, nunca rellenar con cero:

- Cliente sin entidad en Syntage o con extracción incompleta → mismo mensaje
  que ya usa `monederos.analizar_cliente`, el tab lo muestra tal cual.
- Ningún candidato del padrón → `"monederos": []`, aviso informativo.
- Candidato que no confirma el patrón → se guarda con `es_real: false`, no se
  descarta en silencio (para diferenciarlo de "no se detectó nada").
- Mes sin PDF/XML descargado → "falta este mes", nunca se rellena con cero.
- PDF/XML que no cuadra contra su subtotal declarado → sospechoso, fuera del
  agregado.
- Mes con comisión de Etapa 1 pero sin total de Etapa 2 → el % de ese mes no
  se calcula, nunca se divide contra un total no confirmado.

## Pruebas

Mismo patrón que ya usan `test_estaciones_monedero.py` y
`test_estado_cuenta_monedero.py`: `syntage` de mentiras con facturas
inventadas para `comision_candidatas` y `revisar_cliente`; tablas/XML
inventados con la misma forma que produce `pdfplumber`/el XML del CFDI para
`reporte_cliente`. Nada de RFC, razón social o montos reales de clientes en
los fixtures — inventados, siguiendo la restricción ya establecida en el plan
anterior.

`_tab_monedero` no lleva prueba automatizada (es despliegue de Streamlit,
como el resto de `front.py`); se verifica a mano abriendo el tablero con
`python nea.py front`.

## Qué queda fuera (a propósito)

- El barrido periódico sobre toda la cartera (la Etapa 1 original,
  `plan_descarga` sobre `barrer_entidades_syntage()`) sigue existiendo por
  CLI para quien quiera correrlo, pero no es lo que dispara el tab.
- Automatizar la descarga del PDF/XML vía la plataforma web de Syntage sigue
  fuera de alcance (ya se descartó en el spec anterior).
- Una tabla en Supabase para este dato: no hay hoy ningún otro módulo que lo
  consuma (a diferencia de `estados_cuenta` o `perfil_empresa`); se agrega el
  día que alguien lo necesite, no antes.
- Comparar la comisión encontrada contra un benchmark de mercado de forma
  automática (ej. "🟢 oportunidad" si > 1.75%): el número se muestra crudo:
  la decisión de negocio la sigue haciendo el operador.
