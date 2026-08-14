# Brief de diseño — Plataforma de onboarding Nea

> Para dárselo a Claude Design. **No contiene datos de clientes reales**: todos los
> nombres, RFC y cifras de los ejemplos son inventados.

---

## 1. Qué es

Nea Card es un emisor mexicano de tarjetas de crédito corporativas, regulado por
la LFPIORPI (ley antilavado). Antes de darle una línea de crédito a una empresa
hay que armar un expediente: validar sus documentos, identificar a sus
beneficiarios controladores, correr un modelo de riesgo y dejar por escrito qué
riesgos se asumen y quién los firma.

Esta plataforma es el tablero interno donde eso se ve y se decide. **No es un
producto para clientes finales.** Lo usan dos o tres personas dentro de Nea.

## 2. Quién la usa

**El operador (usuario principal).** Dirige la empresa, no programa y no quiere
usar la terminal. Necesita responder cuatro preguntas sin ayuda de nadie:

1. ¿Cómo van todos mis clientes en proceso?
2. ¿Cuál está atorado y por qué?
3. ¿Este cliente califica, y qué dice el modelo?
4. ¿Qué le falta a este expediente para avanzar?

**El oficial de cumplimiento.** Entra a revisar observaciones y firmas. Le
importa el rastro documental, no la estética.

## 3. La regla dura del producto

**La plataforma no autoriza.** Se puede ver todo y no se puede aprobar nada. No
hay ni debe haber un botón "Aprobar". Autorizar una línea exige, por cada riesgo
que se asume, una justificación escrita y el nombre de quien la firma; un botón
en una pantalla convierte eso en un clic el primer día que haya prisa.

Cualquier diseño que ponga un CTA primario tipo "Aprobar" o "Autorizar" está
mal. El CTA de esta app es *entender*, no *actuar*.

## 4. La tensión de diseño más importante

Casi todo dashboard esconde las salvedades para verse limpio. **Aquí la salvedad
es el contenido.** Tres ejemplos reales del producto:

- Un score de `0.5163` no significa nada sin la leyenda de que se calculó sobre
  3 de 4 módulos y que **no es comparable** contra un score completo.
- Una línea propuesta de `$0.00` es distinta de "el modelo no propone nada". Lo
  primero se lee como que propuso cero pesos.
- Un campo vacío **a propósito** (no se pide ese documento, y por esta razón) se
  ve idéntico a un campo **faltante** si el diseño no los separa. Uno es una
  decisión y el otro es trabajo pendiente.

El principio del negocio detrás: **la ausencia de un dato no es un dato
desfavorable.** El diseño tiene que dejar que eso se lea, no aplanarlo en un
número bonito. Si hay que elegir entre elegancia y que la salvedad se vea, gana
la salvedad — pero el reto es no tener que elegir.

## 5. Arquitectura actual

```
Sidebar (siempre visible)
└── Lista de expedientes: "Tablero" + un renglón por cliente

Pantalla A · TABLERO
├── 5 métricas: Expedientes · Atorados · En firma · Pendientes del cliente · Línea autorizada
├── Tabla de expedientes, un renglón por cliente:
│     folio · razón social · etapa · días en etapa · score+veredicto · qué lo detiene
└── Aviso al pie con los atorados

Pantalla B · UN CLIENTE
├── Encabezado: razón social
├── 4 métricas: Folio · Etapa · Línea solicitada · Línea autorizada
├── Banda "Qué lo detiene: ..."   (solo si está detenido)
└── 8 pestañas
      1 Score          — el modelo de riesgo, desglosado
      2 Perfil         — la empresa según el SAT
      3 Observaciones  — los hallazgos de la revisión
      4 Banco y fiscal — estados de cuenta y declaraciones
      5 Documentos     — qué papeles hay, cuándo vencen
      6 Historial      — cuánto lleva en cada etapa
      7 Resumen ejecutivo — el documento para comité, texto plano
      8 Alta en la base operativa — 63 campos para copiar y pegar
```

### Qué hay en cada pestaña

**1 · Score.** Score (4 decimales), veredicto, y línea que propone el modelo.
Luego cuatro módulos con su peso y su puntaje en barra de progreso:

| Módulo | Peso |
|---|---|
| Estados de cuenta | 27.5% |
| Declaración anual | 27.5% |
| Buró de crédito | 25% |
| Perfil de empresa | 20% |

Un módulo puede salir "sin datos — sale del promedio" y los pesos de los que
faltan se reparten entre los demás. Eso **tiene** que verse. Abajo, dos
desplegables: cada variable con su peso dentro del módulo (unas 25 variables), y
con qué datos se calculó. Al final, evaluaciones anteriores.

**2 · Perfil.** Dos bloques con distinta procedencia, y la distinción importa:
lo **derivado** de la API fiscal (estado, alta ante el SAT, empleados, actividad,
CFDI emitidos, facturación, cliente y proveedor principal con su %) y lo
**capturado por el operador** (giro, procedencia del lead, presencia digital).
Más una lista de banderas de riesgo en rojo.

**3 · Observaciones.** Lo más denso de la app: hasta ~30 por expediente, cada una
con severidad (alta / intermedia / baja), estado (abierta / aceptada / resuelta),
un título, un cuerpo largo, y si fue aceptada, su justificación escrita y la
firma de quien la aceptó. Hoy son acordeones con filtro por estado. **Es la
pestaña que más necesita diseño**: la justificación de un riesgo puede ser un
párrafo de 15 líneas y es información legal, no decorado.

**4 · Banco y fiscal.** Tabla de estados de cuenta por corte (saldo promedio,
mínimo, máximo, depósitos, retiros) + gráfica de línea del saldo. Tabla de
declaraciones anuales por ejercicio (ingresos, utilidad, activo y pasivo a corto
plazo, capital contable). Alerta si el capital contable es negativo.

**5 · Documentos.** Tabla: tipo, sujeto, fecha de emisión, vencimiento, legible.

**6 · Historial.** Cuántos días lleva o llevó en cada etapa.

**7 · Resumen ejecutivo.** Un documento de texto de ~200 líneas, monoespaciado,
que se genera para el comité. Hoy se muestra en un bloque de código. Se puede
rediseñar como documento, pero **su texto no se edita ni se resume**.

**8 · Alta en la base operativa.** 63 campos agrupados en 6 secciones, cada uno
con su valor listo para copiar (botón de copiar por campo), su nota al pie
explicando de dónde salió, y tres estados visuales distintos: valor normal,
`FALTA` (hay que conseguirlo), y `— vacío a propósito —` (decisión, con motivo).
Arriba, la lista de lo que hay que resolver antes del alta.

## 6. Vocabulario de estados (el corazón del sistema visual)

**Etapas del expediente** — orden fijo, es un flujo:
`apertura → validación → riesgo → generación → firma → cerrado`

**Veredicto del modelo** — cuatro valores, con color actual:

| Veredicto | Color hoy | Significa |
|---|---|---|
| Aprobado | `#1B8A5A` verde | score ≥ 0.70 |
| Comité | `#B8860B` ámbar | score ≥ 0.50, lo decide una persona |
| Rechazado | `#C1372B` rojo | score < 0.50 |
| Sin datos suficientes | `#777777` gris | **no es un rechazo** |

Ese último es importante: gris ≠ rojo. La falta de datos no es una mala nota.

**Severidad de observación** — tres niveles:

| Severidad | Color hoy | Significa |
|---|---|---|
| alta | `#C1372B` | documento inválido, hay que reponerlo |
| intermedia | `#B8860B` | se puede aceptar por escrito |
| baja | `#777777` | queda anotado |

**Estado de observación**: abierta / aceptada / resuelta. "Aceptada" no es
"resuelta": el riesgo sigue ahí, alguien lo firmó.

**Días en etapa**: si pasa el umbral de su etapa, el expediente está *atorado* y
hoy se marca en coral con ⚠.

## 7. Marca

- Coral Nea: **`#F1654B`** — es el único color de marca definido. Hoy se usa en
  el título y para marcar atorados.
- Todo lo demás son los defaults de Streamlit (fondo blanco, tipografía del
  sistema, gris azulado en los bordes).
- No hay logotipo en la app. No hay tipografía definida. **Hay espacio para
  proponer un sistema completo.**

## 8. Restricción técnica (importante)

El front está hecho en **Streamlit** (Python). No es negociable a corto plazo, y
por una razón: este front *llama* al validador y al modelo de riesgo en vez de
reimplementarlos. Un front en otro lenguaje tendría que copiar las reglas de
negocio, y dos copias de una regla se separan siempre; la que se separa en
silencio es la que autoriza créditos.

Lo que eso significa para el diseño:

**Se puede portar bien:** paleta, tipografía, escala de espaciado, tarjetas,
badges y chips, tratamiento de tablas, encabezados, jerarquía tipográfica,
estilos de métrica, acordeones, barras de progreso, iconografía simple, modo
oscuro. Todo eso se inyecta con CSS y con componentes armados en HTML.

**No se puede portar:** layouts arbitrarios de rejilla, animaciones complejas,
navegación con router propio, drag & drop, gráficas totalmente personalizadas.

**Cómo entregar el diseño para que sea portable:** HTML + CSS autocontenido, con
las variables de color y tipografía declaradas en `:root`, y los componentes
como bloques identificables. Vale usar clases propias; hay que evitar depender de
un framework de JS.

## 9. Escala real

- Hoy: 2 expedientes. Volumen esperado: ~10 clientes nuevos al mes.
- La tabla del tablero no va a tener 500 renglones. Va a tener entre 5 y 40.
  **Se puede diseñar para densidad baja y lectura cómoda**, no hace falta una
  tabla de datos industrial.
- La vista de cliente sí es densa: 8 pestañas, ~30 observaciones, 63 campos.

## 10. Qué necesito de vuelta

En orden de importancia:

1. **El sistema visual**: paleta completa (claro y oscuro) construida alrededor
   del coral `#F1654B`, escala tipográfica, espaciado, radios, sombras. Con los
   cuatro veredictos y las tres severidades resueltos como colores semánticos que
   se distingan también para alguien con daltonismo — hoy dependen solo del tono.
2. **Las dos pantallas completas en HTML**: el tablero y la vista de un cliente
   (con la pestaña de Observaciones abierta, que es la más difícil).
3. **Los componentes sueltos**: tarjeta de métrica, renglón de expediente, chip
   de etapa, badge de veredicto, badge de severidad, tarjeta de observación con
   su justificación firmada, campo copiable con nota y con sus tres estados
   (valor / FALTA / vacío a propósito), barra de módulo con peso.
4. **Una crítica de la arquitectura de información**, si la ves mal. Ocho
   pestañas puede ser demasiado. Si hay una organización mejor, dímela — pero
   sabiendo que ningún dato se puede esconder para simplificar.

## 11. Lo que el diseño NO debe hacer

- No poner un botón de aprobar, autorizar, rechazar o firmar.
- No esconder las salvedades del score detrás de un tooltip. Se leen o no se leen.
- No convertir "sin datos" en un cero, ni pintarlo de rojo.
- No resumir ni truncar la justificación de un riesgo aceptado: es un documento
  legal y se lee completo.
- No inventar métricas que la plataforma no calcula (no hay "probabilidad de
  impago", no hay "salud del cliente", no hay tendencias).
- Nada de modo demo con datos falsos bonitos: los expedientes reales están a
  medias, con módulos sin datos y observaciones abiertas. **Ese es el estado
  normal**, no el caso de error.

---

## Anexo · Datos de ejemplo para maquetar (inventados)

**Tablero**

| Folio | Razón social | Etapa | Días | Score | Veredicto | Qué lo detiene |
|---|---|---|---|---|---|---|
| DEMO-01 | ABARROTES DEL NORTE, S.A. de C.V. | riesgo | 12 ⚠ | 0.5163 | Comité | Falta el buró del acreditado |
| DEMO-02 | TRANSPORTES XY, S. de R.L. | validación | 3 | — | sin evaluar | 2 documentos pendientes del cliente |
| DEMO-03 | SERVICIOS INTEGRALES ZZ, S.C. | firma | 1 | 0.7420 | Aprobado | — |
| DEMO-04 | COMERCIAL EJEMPLO, S.A. | riesgo | 21 ⚠ | 0.3100 | Rechazado | — |
| DEMO-05 | DISTRIBUIDORA MODELO, S.A. | apertura | 2 | — | Sin datos suficientes | Sin estados de cuenta |

Métricas del tablero: Expedientes **5** · Atorados **2** · En firma **1** ·
Pendientes del cliente **6** · Línea autorizada **$310,000.00**

**Score de DEMO-01**

Score `0.5163` → **Comité**. Línea que propone el modelo: *no propone*.
Aviso: “Calculado sobre 3 de los 4 módulos. Los pesos de los que faltan se
repartieron entre los demás, así que **no es comparable** contra un score
completo. Falta: buró de crédito.”

| Módulo | Peso | Puntaje |
|---|---|---|
| Perfil de empresa | 20% | 0.5750 |
| Buró de crédito | 25% | sin datos — sale del promedio |
| Estados de cuenta | 27.5% | 0.3800 |
| Declaración anual | 27.5% | 0.6100 |

**Observación aceptada (ejemplo de la más difícil de maquetar)**

> **[intermedia · aceptada]** El saldo promedio no alcanza la línea solicitada
>
> El saldo promedio de la cuenta entregada es de $18,545 contra una línea de
> $50,000 semanales.
>
> **Justificación de la aceptación** — Se acepta porque la facturación real de
> la empresa es de $1.16M al mes según CFDI, y porque existe obligado solidario
> con capacidad demostrada. Queda como el punto a revisar en la primera
> renovación.
>
> *Firma: Comité de crédito — Nombre Apellido*

**Campo copiable (los tres estados)**

```
Régimen Fiscal:          [ 601 General de Ley Personas Morales ]  ⧉
Comprobante de domicilio: — vacío a propósito —
   No se pide. El domicilio ya viene en la CSF y el campo no es obligatorio.
Teléfono:                 FALTA
```
