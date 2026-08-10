# Plataforma de onboarding — Nea Card

Convierte los documentos de un cliente nuevo en su paquete de contratos listo
para firma, y lleva el registro de en qué va cada expediente.

## Instalar (una sola vez)

```bash
pip install -r requirements.txt
```

Eso es todo. Los expedientes se guardan en la carpeta `expedientes/` de tu
computadora y funciona sin internet.

## Usar

Todo pasa por un solo comando. Sin argumentos, muestra el tablero: todos los
expedientes y qué detiene a cada uno.

```bash
python nea.py
```

**El paso a paso completo de un cliente nuevo está en [OPERAR.md](OPERAR.md)**,
incluyendo qué partes necesitan una persona y por qué.

### Cliente nuevo

Necesitas su Constancia de Situación Fiscal en PDF (la del SAT, no una foto):

```bash
python nea.py nuevo "C:\ruta\a\la\csf.pdf"
```

Lee la constancia, saca razón social, RFC, domicilio y régimen, te asigna el
folio, y te pregunta los datos que captura ventas. Si el contribuyente no está
ACTIVO, se detiene: el expediente no debe abrirse.

### Ver qué falta

```bash
python nea.py estado RAMSOJ-01
```

Te lista exactamente qué impide generar los contratos. Son las nueve compuertas
de la etapa 6: línea autorizada, representante validado con facultad para
suscribir títulos de crédito, estados de cuenta suficientes, observaciones
resueltas o aceptadas por escrito, y firma de cumplimiento sobre el beneficiario
controlador.

### Agregar la CSF de un obligado solidario o un beneficiario

```bash
python nea.py csf RAMSOJ-01 "C:\ruta\csf_del_obligado.pdf" obligado
python nea.py csf RAMSOJ-01 "C:\ruta\csf_del_beneficiario.pdf" beneficiario
```

Solo llena los campos vacíos: nunca pisa lo que ya validaste.

### Generar el paquete

```bash
python nea.py generar RAMSOJ-01
```

Antes de generar te avisa qué campos van a salir en blanco. Los documentos
quedan en `expedientes/FOLIO_paquete/`, más el manifiesto que agrupa quién firma
qué.

### Subirlo a Drive

```bash
python nea.py subir RAMSOJ-01
```

Requiere haber configurado Drive (ver `SETUP_DRIVE.md`).

## Llenar lo que falta

Los datos que no salen de la CSF —facultades del representante, estructura
accionaria, decisión de riesgo— se editan a mano por ahora, en el archivo
`expedientes/FOLIO.json`. Es texto: lo abres con el Bloc de notas, buscas el
campo y escribes el valor entre las comillas.

Automatizar esa captura es lo que sigue en la ruta de construcción.

## Configuración opcional

| Qué | Para qué | Instrucciones |
|---|---|---|
| Supabase | Que los datos vivan fuera de tu laptop y poder consultar la exposición agregada | `SETUP_SUPABASE.md` |
| Google Drive | Bajar documentos y subir el paquete sin hacerlo a mano | `SETUP_DRIVE.md` |

Sin ninguna de las dos, la plataforma funciona completa en tu computadora.

## Dónde está cada cosa

| Archivo | Qué hace |
|---|---|
| `nea.py` | El comando único. Lo demás son piezas que este usa |
| `ESPECIFICACION.md` | Alcance, decisiones de arquitectura y las nueve etapas |
| `schema_expediente.py` | La estructura del expediente y las nueve compuertas |
| `extraer_csf.py` | Lee la Constancia de Situación Fiscal |
| `generadores/` | Los ocho documentos del catálogo |
| `db.py` | Habla con Supabase |
| `drive_cliente.py` | Habla con Google Drive |

## Sobre los datos de clientes

Este repositorio guarda **solo el programa**. Los expedientes con CURP, RFC y
domicilios de personas reales viven en tu disco, en Drive y en Supabase, y están
excluidos de git a propósito. No los subas a GitHub.
