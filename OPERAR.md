# Cómo se opera

Todo pasa por `python nea.py`, desde una terminal en la carpeta del proyecto.

## Dónde ves el estatus

En el navegador:

```bash
python nea.py front
```

Se abre solo. Del lado izquierdo eliges el tablero o un cliente; en el cliente
hay siete pestañas: score con el desglose por módulo y por variable, perfil,
observaciones, banco y fiscal, documentos, historial y el resumen ejecutivo. Para
cerrarlo, Ctrl+C en la terminal.

**El front no autoriza.** Se ve todo y no se aprueba nada, a propósito: autorizar
exige una justificación escrita por cada riesgo que se asume y el nombre de quien
la firma, y un botón convierte eso en un clic el primer día que haya prisa.

Si prefieres la terminal, lo mismo sin navegador:

```bash
python nea.py
```

Eso es el tablero. Un renglón por expediente, ordenados por etapa y, dentro de
cada etapa, por los que llevan más tiempo. La columna **QUE LO DETIENE** dice
qué falta, ya resuelto en el orden en que hay que atacarlo: primero lo que le
toca al cliente, porque eso es lo que tarda.

El `!` junto a los días marca los que llevan más de lo normal en su etapa
—apertura 3 días, validación 7, riesgo 3, generación 2, firma 10—. Para ver solo
esos:

```bash
python nea.py tablero --atorados
```

Dos comandos más de consulta:

```bash
python nea.py estado LLOSA-01       # el detalle: observaciones, qué falta
python nea.py historial LLOSA-01    # por dónde pasó y cuánto tardó en cada etapa
```

No hay otra pantalla de estatus, y es a propósito. Antes la pantalla de inicio
contaba una cosa y el tablero calculaba otra, y llegaron a contradecirse sobre el
mismo expediente. Cuando dos tableros no coinciden, no se cree ninguno.

---

## Un cliente nuevo, de principio a fin

Los pasos van en este orden porque cada uno depende del anterior. Lo que dice
**tú** es lo que no puede hacer el sistema.

### 1. Abrir el expediente

Necesitas su Constancia de Situación Fiscal en PDF —la del SAT, no una foto—.

```bash
python nea.py nuevo "C:\ruta\a\la\csf.pdf"
```

Lee la CSF, propone folio, y si el contribuyente no está ACTIVO se detiene ahí
mismo: no se abre expediente de alguien suspendido.

### 2. Traer los documentos del vendedor

La carpeta del vendedor **no se toca**. Los documentos se copian a la nuestra con
la nomenclatura del proyecto. Hoy este paso lo hago yo desde el chat, leyendo su
carpeta y copiando; no está automatizado porque cada vendedor organiza distinto.

### 3. Revisar y pedir lo que falta

```bash
python nea.py estado LLOSA-01        # qué falta y de qué gravedad
python nea.py solicitud LLOSA-01     # el texto que ventas le reenvía al cliente
```

La solicitud sale numerada, agrupada por empresa —cliente y obligado solidario
juntos— y sin jerga. Se manda **una sola vez**: cada vuelta de solicitudes es una
oportunidad de perder al cliente.

### 4. Buró de crédito — **tú**

Se genera en el portal de Buró Empresas con la VPN. Yo no guardo esas
credenciales; tú entras y yo te acompaño extrayendo los datos del reporte. Ojo:
**un reporte de buró no se puede volver a consultar**, así que en cuanto salga se
guarda el PDF.

### 5. Syntage

Extrae los 29 recursos del SAT y guarda todo, no solo lo que el modelo consume.
Requiere que el cliente haya autorizado su CIEC en Syntage.

### 6. Perfil de empresa

```bash
python nea.py perfil LLOSA-01
```

Deriva solo lo que se puede derivar —estado, antigüedad, giro sugerido,
empleados, concentraciones, las 13 banderas de riesgo— y te pregunta únicamente
lo que nadie más sabe: confirmar el giro, de dónde llegó el prospecto, y la
presencia digital.

### 7. Correr el modelo

```bash
python nea.py riesgo LLOSA-01
```

Si la compuerta de riesgo está cerrada **no corre**, y te dice qué falta. Eso es
deliberado: un score calculado sobre módulos incompletos no es un score bajo, es
un número que no describe a nadie y que luego se cita como si sí.

### 8. El resumen ejecutivo

```bash
python nea.py resumen LLOSA-01
```

Lo que el score **no** captura. Es el documento con el que se decide, y cierra
sin recomendación a propósito.

### 9. Autorizar o rechazar — **tú**

No hay comando todavía: se registra en el expediente. Autorizar exige, por cada
riesgo que se asume, una justificación escrita y el nombre de quien la firma. La
compuerta no abre sin eso, y no es burocracia: es lo que contesta, en un año,
"¿sabían esto cuando firmaron?".

### 10. Generar y subir

```bash
python nea.py generar LLOSA-01
python nea.py subir LLOSA-01
```

`generar` avisa qué campos van a salir en blanco antes de escribir los PDFs.
`subir` deja los documentos de firma en `3 Documentos generados`, los análisis en
`2 Análisis interno`, y si ya había una versión anterior la manda a
`0 Superados` en vez de pisarla.

### 11. Mandar a firma

```bash
python nea.py firma LLOSA-01 --subir
```

Sube el paquete a WeeTrust **como borrador**, con las divisiones y los niveles de
firma ya puestos. El envío se hace desde la plataforma de WeeTrust: este comando
no puede mandarlo.

### 12. Alta en la base operativa — **tú**

Una vez firmado, en el front: pestaña **Alta en la base operativa**. Trae los
campos del formulario de Django en el orden de la pantalla, cada uno con su botón
de copiar, las fechas ya en `aaaa-mm-dd` y el régimen fiscal con su clave (el
dropdown la lleva, la CSF no).

```bash
python nea.py alta LLOSA-01     # lo mismo, en texto plano
```

Arriba de la lista sale lo que hay que resolver: campos sin dato y observaciones
altas abiertas. Los campos que van vacíos **a propósito** —el logo, el referido
cuando el prospecto vino de un canal propio— salen marcados como tales y no
aparecen ahí; un campo vacío y un campo faltante no son lo mismo.

Dos cosas para revisar a ojo:

- El **nombre partido** en nombre / paterno / materno. Cuando la CURP lo
  comprueba no se dice nada; cuando no, sale una nota que manda a la
  identificación oficial. Esa nota hay que atenderla.
- Los **dropdowns**. Si el catálogo del Django no trae exactamente la opción que
  proponemos, manda el catálogo.

---

## Lo que todavía necesita una persona

Con un cliente al mes no importa. Con diez, son unas cuatro horas al mes:

- **el buró**, porque es un portal con VPN y credenciales que rotan cada 30 días
- **los CEPs de Banxico**, que se consultan uno por uno
- **traer los documentos** de la carpeta del vendedor
- **el alta en el Django**, mientras no haya conexión directa. Los campos ya
  salen armados; lo que falta es pegarlos

Ahí está el siguiente proyecto, no en una pantalla más bonita.

## Si algo se rompe

```bash
python nea.py drive     # revisa las credenciales de Drive y prueba la conexión
python db.py probar     # revisa la conexión a Supabase
```

Y antes de confiar en cualquier cambio al código:

```bash
python tests/test_validador.py
python tests/test_modelo_riesgo.py
```

Las pruebas son la compuerta: si una está en rojo, el cambio no se sube.
