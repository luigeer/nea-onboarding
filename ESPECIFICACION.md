# Plataforma de Onboarding — Nea Card / Grit Payment Solutions

Especificación funcional, decisiones tomadas y estado del código.
Documento de contexto para continuar el desarrollo en Claude Code.

Última actualización: 29 de julio de 2026

> **Nota del 6 de agosto de 2026 — la arquitectura cambió.** El estado de los
> expedientes ya **no vive en Notion** sino en una base de datos propia
> (Supabase), y la plataforma corre local con un solo comando, `nea.py`. El
> resto de este documento —las nueve etapas, las compuertas, el catálogo de
> documentos y los criterios de PLD— sigue vigente y es la fuente de verdad
> funcional. Donde diga "Notion", léase "la base de datos". Para operar, ver
> `LEEME.md`.

---

## 1. Alcance

Automatizar el onboarding de clientes de Nea desde la recolección de documentos
hasta la generación de los contratos, con seguimiento del estado de cada expediente.

**Entrada:** los documentos del cliente en una carpeta de Google Drive.
**Salida:** el paquete de contratos listos para firma, más el manifiesto de firmantes.

**Volumen:** de uno a cinco onboardings por semana. Toda decisión de arquitectura
está calibrada a ese volumen; arriba de veinte por semana hay que revisarla.

**Usuarios:** ventas (recolecta y consulta estado), finanzas (abre expedientes),
riesgo (autoriza líneas), cumplimiento (firma determinaciones de PLD), y Luis
(dispara la generación y da de baja expedientes).

**Fuera de alcance por ahora:** la firma electrónica con WeeTrust y la integración
con Syntage quedaron aplazadas, pero el diseño las asume existentes.

---

## 2. Decisiones de arquitectura

### 2.1 No hay orquestador tipo n8n

El proceso tiene dos mitades de naturaleza opuesta:

- **Trabajo por cliente** (leer expediente, validar, determinar beneficiario
  controlador, generar documentos). Intensivo en juicio, ocurre en una sentada,
  de una a cinco veces por semana. Un orquestador aquí sería un caparazón cuyo
  trabajo real es llamar a un modelo.
- **La espera** (el cliente tarda días en firmar, la confirmación llega de noche).
  Es lo único que necesita algo siempre encendido.

La segunda mitad se resuelve con consulta programada diaria en lugar de webhook:
a este volumen nadie necesita saber en treinta segundos que el cliente firmó.

**Componentes:**

| Pieza | Quién la usa | Para qué |
|---|---|---|
| Repo con Claude Code | Luis y perfiles técnicos | Motor: generadores, extractores, clientes de API |
| Cowork | Cumplimiento, quizá ventas | Superficie humana sin terminal |
| Notion | Todos | Estado, kanban por etapa, captura de flags |
| Tarea programada diaria | Nadie | Consulta firmas pendientes, marca los atorados |

**Lo que se pierde y por qué no importa:** el log de ejecuciones de n8n tiene valor
en un proceso PLD. Pero WeeTrust ya expone `logsStatusObj` con `operationType`,
`operationBy`, `sourceIP` y `addedOn`, o sea la traza completa de la ceremonia de
firma; más el historial de páginas de Notion para los cambios de etapa.

### 2.2 Los archivos en Drive, el estado en Notion

Drive guarda los documentos; Notion guarda el registro estructurado y el estado.
**No hay carpetas de estado**: mover carpetas entre estados es el paso manual que
se rompe. Una sola fuente de verdad para el estado.

---

## 3. Infraestructura

### 3.1 Estructura de Drive

```
Nea — Expedientes de Clientes/
├── _Plantillas y formatos/
├── ADMINISTRADORA DE CENTROS COMERCIALES CA, S.A. DE C.V. — ACC-01/
│   ├── 1 Documentos del cliente/
│   │   └── 0 Superados/          ← documentos reemplazados, no se borran
│   ├── 2 Análisis interno/       ← modelo de riesgo, reporte de buró, IGR
│   ├── 3 Documentos generados/   ← salida de la etapa 6
│   └── 4 Documentos firmados/    ← salida de la firma electrónica
└── CEVER — Grupo/
    ├── _Documentos compartidos del grupo/   ← INE y CSF de los beneficiarios
    └── [entidad] — CEVER-NN/
```

Creada en `https://drive.google.com/drive/folders/17_Q_pWg8VQvgDvR7_HESb8ows5AgYT8A`

**Pendiente:** debe vivir en una **unidad compartida**, no en el Drive personal de
una persona. Hoy los expedientes son propiedad de cuentas individuales, lo que
significa que la conservación de cinco años que exige la LFPIORPI depende de que
esa cuenta siga existiendo. Solo un administrador del Workspace puede crear la
unidad compartida. Al moverla, los identificadores de carpeta se conservan.

### 3.2 Folio

Formato: `ACRÓNIMO-NN`, donde el acrónimo es del grupo y NN es el número de entidad
dentro del grupo. Ejemplos: `CEVER-24`, `CEVER-25`, `ACC-01`, `RAMSOJ-01`.

Ventas ya usaba ese contador de entidades por holding (existían carpetas
`24 CEVER AUTOMOTRIZ SANTA FE` y `25 CEVER SAN ANGEL`). El acrónimo ya se usaba
informalmente en los nombres de archivo (`ACC_ABRIL`, `CSF_ACC_MAYO`).

El folio se asigna en la etapa 0 y amarra el registro de Notion, la carpeta de
Drive y los documentos generados. Antes se ponía al final, cuando alguien se
acordaba, y quedaba vacío con frecuencia.

### 3.3 Nombre de carpeta

`RAZÓN SOCIAL — FOLIO`, con guion largo.

El separador no es cosmético: las razones sociales contienen comas, puntos y
guiones cortos (`S.A. de C.V.`, `Build.ify`), así que un guion corto no sirve para
partir el nombre por código. El guion largo casi nunca aparece en una razón social.

La razón social sale de la CSF, no de lo que teclea ventas. Los nombres actuales
no están estandarizados: hay espacios dobles, mayúsculas inconsistentes,
abreviaturas (`CEVER AUTOMOTIZ STA. FE`), y sobre todo nombres comerciales en
lugar de razones sociales (`Koolteck`, `Limre`, `RAM`).

**Clasificación de archivos por contenido, no por nombre.** Ventas suelta los
archivos en `1 Documentos del cliente` y el sistema decide qué es cada cosa. Pedir
que ventas aprenda una convención no se sostiene.

---

## 4. Las nueve etapas

### Etapa 0 — Apertura del expediente

**Disparador:** finanzas abre el expediente cuando ventas da el ok. El evento
concreto es la CSF de la persona moral cargada en `1 Documentos del cliente`.

**Automático:**
1. Lee la CSF y extrae razón social, RFC, régimen de capital, domicilio fiscal,
   actividad económica, régimen fiscal, inicio de operaciones y situación
2. Deriva el tipo de cliente por longitud del RFC (12 = moral, 13 = física) y por
   los regímenes declarados (PFAE si trae Actividades Empresariales)
3. Si hay más de una CSF, toma la de **emisión** más reciente, no la de carga
4. Descarta las CSF de personas físicas: son de los beneficiarios controladores
5. Busca duplicados por RFC contra expedientes existentes
6. Asigna folio y renombra la carpeta
7. Crea el registro en Notion en etapa "Expediente en recolección"

**Compuerta de rechazo temprano:** si la situación del contribuyente no es ACTIVO,
el expediente no se abre.

**Captura manual de ventas (9 campos):** representante legal propuesto, su correo,
su teléfono, contacto operativo y su correo, línea solicitada, plazo, número de
tarjetas, y si requiere domiciliación. El flag de obligado solidario nace vacío:
lo llena riesgo en la etapa 5.

**El correo del representante legal es punto único de falla.** Los documentos y las
ceremonias de firma se enrutan ahí. Debe ser obligatorio para cerrar la etapa, y
conviene un correo de bienvenida que confirme que la dirección existe antes de
depender de ella.

**El representante legal de la etapa 0 es hipótesis, no dato.** Quién puede firmar
depende de las facultades en la escritura, y eso se sabe en la etapa 2. Por eso hay
campo `propuesto` y campo `validado` separados: con Enercrea se acabó firmando con
Mónica Morales y no con la Administradora Única, y esa traza importa.

### Etapa 1 — Recolección

La recolección **no es un evento, es un ciclo**. En el expediente de ACC los
documentos entraron a lo largo de nueve días, con dos reemplazos.

**Documentos obligatorios, persona moral:**

| Documento | Criterio |
|---|---|
| CSF de la persona moral | Máximo 3 meses de emitida. Es el disparador |
| Escritura constitutiva | Testimonio o copia certificada |
| Comprobante de domicilio | Máximo 3 meses |
| Identificación oficial vigente del representante | Credencial para votar, pasaporte, cédula profesional, licencia o documento migratorio |
| Autorización de buró del representante | Vigencia 3 años |
| Credencial del SAT | Requisito del cliente para las extracciones de Syntage |
| Cotización | |
| Estados de cuenta | 3, o 6 si la línea supera $200,000 |
| Identificación oficial vigente de cada beneficiario controlador | |
| CSF de cada beneficiario controlador | Práctica de Nea, más de lo que exige el Manual |

**Condicionales:** poderes si no están en la constitutiva · acta de asamblea si la
razón social de la CSF difiere de la constitutiva · documentos del obligado
solidario si aplica, o referencia a su expediente si ya es cliente · estados de
cuenta de cuentas en otra divisa si existen.

**Persona física / PFAE:** CSF, identificación oficial vigente con fotografía,
comprobante de domicilio, constancia de que actúa por cuenta propia o de un
tercero, autorización de buró, credencial SAT, cotización y estados de cuenta.
Condicionales: si actúa por cuenta de tercero se dispara el análisis de
beneficiario controlador; si comparece apoderado, carta poder más identificación y
comprobante de domicilio del apoderado. No aplican escritura constitutiva, poderes
societarios, asambleas ni estructura accionaria.

**Asambleas:** solo la constitutiva es obligatoria, más los poderes si no están en
ella, más el acta de asamblea en caso de cambio de razón social. Ese último caso es
detectable solo: si la razón social de la CSF difiere de la constitutiva, se pide.

**El checklist se expande al leer.** Hay tres expansiones dinámicas: al leer la
constitutiva aparecen los beneficiarios controladores y con ellos su identificación
y CSF; al comparar razones sociales puede aparecer el acta de cambio; al leer los
poderes pueden aparecer cofirmantes si es mancomunado. La lista completa no se
conoce hasta haber leído todo, y por eso la recolección es un ciclo.

**Reemplazos:** cuando entra un documento del mismo tipo que uno ya clasificado, el
anterior se mueve a `0 Superados`. No se borra: la trazabilidad se conserva y el
expediente vigente queda sin ambigüedad. En ACC quedaron dos CSF de la empresa y
dos estados de cuenta de abril, sin marca de cuál rige.

**Notificación:** se avisa a ventas **solo cuando la lista de faltantes cambia**.
Notificar en cada cambio produce siete avisos en nueve días y ventas los ignora.

**Dos salidas:** un resumen breve en lenguaje de cliente para que ventas lo copie o
lo muestre, y el reporte completo para riesgo y cumplimiento. Hoy solo existe el
segundo y ventas traduce a mano.

**Compuerta:** cierra el paso a riesgo, no a firma. La baja del expediente es
manual y solo la hace Luis; conviene una vista de expedientes con más de treinta
días sin movimiento.

### Etapa 2 — Validación de fondo

La etapa 1 responde si están todos; la etapa 2, si sirven; la etapa 3, qué dicen.
Técnicamente las tres leen los mismos documentos en una pasada: la separación es de
compuertas, no de procesamiento.

**Vigencias:**

| Documento | Regla |
|---|---|
| CSF | Máximo 3 meses de emitida |
| Comprobante de domicilio | Máximo 3 meses |
| Identificación oficial | Vigente. Criterio Nea, más estricto que el Manual, que admite hasta 2 años de vencida |
| Autorización de buró | 3 años |
| Estados de cuenta | Hasta el último periodo cuyo corte tenga más de 5 días |

La regla de los cinco días: el 4 de agosto, el corte de julio ocurrió hace cuatro
días y todavía no se exige, así que junio es el último obligatorio. El 6 de agosto,
julio ya se exige. Funciona igual para clientes cuyo corte no cae a fin de mes.

**Legibilidad:** documento ilegible es advertencia con solicitud de reemplazo.

**Coherencia entre documentos:** razón social entre CSF, constitutiva y cotización
(con la excepción del cambio de denominación) · RFC entre CSF, constitutiva y
autorización de buró · nombre del representante entre identificación, poder,
autorización de buró y cotización · **titular de los estados de cuenta igual al
cliente** (en grupos es fácil que lleguen los de la tenedora o de una hermana, y el
análisis de riesgo quedaría sobre el flujo de otra entidad) · beneficiarios de la
constitutiva contra las identificaciones y CSF entregadas.

**Validación de facultades del representante legal.** Es la más consecuente de todo
el flujo. Árbol de decisión:

1. ¿Tiene facultad para suscribir títulos de crédito? Si no → solicitar
   representante elegible, **incluyendo la lista de quién sí lo es** según la
   constitutiva, con nombre y fundamento
2. ¿La ejerce individualmente? Si es mancomunado → recabar identificación de todos
   los cofirmantes y el flujo continúa
3. ¿Hay límite de monto? Si el límite en pesos es menor a la línea → representante
   no apto

Produce el campo `representante_legal.validado`, que alimenta todas las ceremonias
de firma. La no revocación del poder queda como declaración del cliente, porque
ningún documento la prueba.

Con Syntage conectado, esto se apoya en `current-powers`, que devuelve por apoderado
los campos `power`, `status`, `expirationDate`, `exerciseJointlyRequired`,
`exerciseJointlyWith` y `exerciseLimitations`. El acta pasa de trabajo principal a
corroboración. Reserva: un poder otorgado ante notario y no inscrito no aparece.

**Manejo de observaciones:** las advertencias no bloquean el avance, pero antes de
firma deben estar resueltas o **formalmente aceptadas por cumplimiento con
justificación escrita**. Sin ese registro la regla no es exigible. Instrumento sin
inscripción en el registro público es advertencia; las inscripciones se pueden
obtener de Syntage.

**Tres salidas:** resumen para ventas, reporte completo en JSON, y el registro de
advertencias abiertas con quién las aceptó y con qué justificación.

### Etapa 3 — Estructuración

Produce el schema del expediente, que es la pieza que alimenta a los ocho
generadores, al registro de Notion y al modelo de riesgo.

**Dos principios de diseño:**

1. **Capas declarado / validado.** Razón social que teclea ventas contra la de la
   CSF; representante propuesto contra validado; línea solicitada contra
   autorizada. Guardar solo el valor final borra la traza de qué cambió y por qué.
2. **Procedencia por campo.** Cada dato carga de qué documento salió. Con eso la
   nota al pie del Formato de Beneficiario Controlador se genera sola en lugar de
   escribirse a mano.

Ver `schema_expediente.py` para la estructura completa. 116 campos hoja.

Detalles resueltos aquí: la CLABE y el nombre del banco para la domiciliación
**salen de los estados de cuenta**, no se teclean. El arreglo `cuentas_bancarias[]`
soporta varias cuentas con divisa distinta, que es el caso del `ACC_ABRIL_USD`.

**Cadena de control:** un solo nivel. El cuadro accionario suele ser de personas
físicas directas, y cuando hay persona moral suele ser un salto. Si aparece un
segundo salto, el sistema lo marca como caso que requiere análisis manual en lugar
de intentar resolverlo mal.

### Etapa 4 — Determinación del beneficiario controlador

**Cascada. Umbral: 25% o más.**

1. **Participación**, directa o indirecta, sobre capital social, derechos de voto o
   derecho a recibir beneficios económicos. Las tres son vías independientes:
   alguien con 10% del capital pero 30% de los votos por acuerdo estatutario
   califica igual.
2. **Control efectivo**, solo si nadie alcanza el umbral. Los tres supuestos del
   Manual: imponer decisiones en asamblea o nombrar o destituir a la mayoría del
   órgano de administración; titularidad de derechos de voto sobre más del 25%; o
   dirigir la administración, la estrategia o las principales políticas.

**Exclusiones que hay que aplicar y decir:** el cliente mismo, los poderdantes o
mandantes cuyos apoderados celebren el acto, el comisario (vigila, no controla), y
el apoderado que solo ejecuta.

**La determinación se funda en participación o control, nunca en el cargo.** En ACC
los dos beneficiarios son a la vez accionistas al 50%, apoderados y consejeros; hay
que fundarla en la participación aunque el resultado coincida. Si se funda en el
cargo, el día que aparezca un director general sin acciones el sistema lo marcará
como beneficiario cuando no lo es.

**PEP:** lo declara el representante legal en la sección IV del Formato A, no el
beneficiario. La sociedad sí sabe si sus accionistas tienen cargos públicos, y es
lo que hace la mayoría de los sujetos obligados en México. Es más débil que una
autodeclaración pero es defendible.

**Screening en listas:** hoy WeeTrust corre al representante legal. El schema deja
`screening[]` como arreglo abierto por sujeto y proveedor para extenderlo a
beneficiarios sin cambiar la estructura. Syntage ya trae verificación de
antecedentes con PEP, medios, penales, legales e internacionales sobre la persona
moral, y probablemente cubre más de lo que se está usando.

**Validación con Syntage:** si existe cualquier asamblea inscrita posterior a la
constitutiva que afecte capital o funcionarios, se pide esa asamblea. Basta comparar
`rpc/actos` contra lo que declara el formato — una consulta, no trece documentos.

**Brecha accionaria:** si la tabla no suma 100% y el faltante es menor a 25%,
advertencia y sigue. Si es de 25% o más, advertencia **y se genera el anexo de
análisis razonado**, porque el faltante podría albergar un beneficiario y el
Formato A afirma bajo protesta que la información es completa.

**Compuerta: firma de cumplimiento en todos los casos.**

**Aviso de privacidad de los beneficiarios controladores:** no se les manda nada a
firmar. El representante legal declara en el Formato A que puso el aviso a
disposición de cada uno, y la sección V los nombra como titulares de los datos. El
tratamiento está mandatado por ley, así que no requiere su consentimiento; lo que sí
subsiste es la obligación de poner el aviso a su disposición, y el cliente es el
canal.

### Etapa 5 — Riesgo y decisión de crédito

La única etapa donde la plataforma no debe intentar decidir. Reúne insumos, dispara
revalidaciones y registra la decisión con su rastro.

**Insumos:** buró de la persona moral (PYME Plus) · estados de cuenta procesados con
el analizador de estados de cuenta · declaración anual vía Syntage · el modelo de
riesgo en Excel.

**Dos revalidaciones hacia atrás.** Es el único punto del flujo donde eso pasa:

1. **Cantidad de estados de cuenta.** Si la línea autorizada cruza los $200,000 y
   solo hay tres, el expediente regresa a recolección. Puede pasar aunque la
   solicitada estuviera por debajo, si riesgo autoriza más de lo pedido.
2. **Límite de monto del poder.** Si la línea autorizada supera el límite del
   representante validado, deja de ser apto y vuelve al árbol de facultades.

**Decisión del obligado solidario:** caso por caso, sin regla. El sistema no la
automatiza, solo la registra. Pero un sí dispara una rama completa y puede regresar
el expediente a recolección, así que no es un checkbox: es una bifurcación.

**Exposición agregada:** dos campos calculados — en cuántos expedientes aparece esta
entidad como obligado solidario, y la suma de esas líneas más la propia. Si la
tenedora tiene línea de un millón y garantiza dos millones más, la exposición real
es de tres, no de uno. Hoy no se ve porque cada expediente se analiza aislado.

**Salida:** resumen ejecutivo con perfil, resultado del modelo desglosado por
módulo, perfil de riesgo, advertencias abiertas y exposición agregada. Se publica en
un canal de Google Chat vía webhook entrante. Luis registra la línea autorizada.

**El modelo propone, no aprueba.** El schema separa `linea_propuesta_modelo` de
`linea_autorizada` para que quede registrado cuándo se apartó del modelo y cuánto.

**Señales no modeladas.** El resumen ejecutivo debe cargar aparte lo que el modelo
no captura. Para ACC: capital contable negativo tres años seguidos, concentración de
clientes con HHI de 2,539 y los dos principales sumando 67%, 69% de la facturación
al cliente principal cancelada, facturación intercompañía del 14%, y nómina en cero
con $19.8 millones de ingresos. Ninguna mueve el score; todas mueven la decisión.

Razón de fondo: los once números que el modelo consume de los estados de cuenta son
cifras de encabezado. `monto_depositos` incluye traspasos entre cuentas propias,
disposiciones de crédito y vencimientos de inversión, así que un cliente que mueve
dinero entre sus propias cuentas infla los depósitos y el modelo lo premia.

**Rechazo:** el expediente rechazado necesita estado propio para no vivir en el
kanban, el motivo debe ser estructurado y no texto libre, y hay que definir cuánto
se conserva documentación con datos personales de quien no llegó a ser cliente (la
obligación de cinco años nace del acto u operación, que aquí no ocurrió).

### Etapa 6 — Generación del paquete

**Se dispara a mano**, una vez registrada la línea autorizada. No es automática.

**Nueve compuertas.** Ninguna genera nada si falla: línea autorizada registrada ·
representante validado · facultad para suscribir títulos de crédito · poder
individual o cofirmantes presentes · límite del poder mayor o igual a la línea ·
cantidad correcta de estados de cuenta · sin faltantes bloqueantes · advertencias
resueltas o aceptadas con justificación · firma de cumplimiento sobre el
beneficiario controlador.

**Matriz de documentos:**

| Documento | Condición |
|---|---|
| Contrato de crédito | Siempre |
| Expediente PLD Anexo 4 | Cliente persona moral |
| Expediente PLD Anexo 3 | Cliente persona física o PFAE |
| Formato de beneficiario controlador | Persona moral con beneficiario identificado |
| Anexo de análisis razonado | Control efectivo, sin identificación, o brecha ≥ 25% |
| Adenda obligado solidario PM | Flag activo y obligado persona moral |
| Adenda obligado solidario PF | Flag activo y obligado persona física |
| Autorización de domiciliación | Flag activo |

**Salida:** archivos separados, no un PDF unido. Convención `FOLIO_Documento.pdf`.

**Manifiesto de firmantes.** Agrupa los documentos por conjunto de **personas**, no
de calidades. Una persona puede firmar el mismo documento en dos calidades — el caso
típico es el representante legal que además es obligado solidario por propio
derecho — y para la firma sigue siendo una sola persona. En RAMSOJ eso reduce de
cuatro grupos a dos.

### Etapa 7 — Firma (aplazada)

WeeTrust, documentado en `developer.weetrust.mx/reference/`. **Corregido en agosto
2026 contra la documentación real:** la autenticación NO es por `X-API-Key` como
decía aquí antes, sino por dos headers en cada llamada, `user-id` y `token`. Y **no
hay sandbox**: toda llamada va a producción.

Flujo: `POST /access/token` → `POST /documents` (el archivo va en el cuerpo, y el
header **`splitPage`** lleva los números de página donde cortar, separados por
comas: así se divide un PDF unido en varios documentos firmables) → `PUT
/documents/signatory` → `GET /documents/{id}` o webhook.

**`PUT /documents/signatory` manda los correos por default.** `disableMailing: true`
los apaga. Ese endpoint también recibe `title` y `message`, o sea el asunto y el
cuerpo del correo de invitación.

Como los firmantes se asignan por `documentID`, para tener una sola ceremonia hay
que **unir con pypdf** los documentos y subirlos como uno, usando `splitPage` para
cortarlos. Eso está implementado en `firma.py` —las reglas de división— y en
`weetrust.py` —el cliente—.

`signatoryObj` permite exigir identificación por `id`, `face`, `ocr` o
`face_login`; `check: true` agrega background check y solo aplica con `face`. Se
usa `face` porque la biometría facial deja mejor soportada la identificación en el
expediente: queda la selfie contra la credencial, no solo la foto de la credencial.

**El envío no se automatiza y no es un pendiente.** Sin sandbox, un bug manda un
contrato a un cliente real y eso no se deshace. `weetrust.py` sube, divide, asigna
firmantes y precarga el correo; el envío lo hace una persona desde la plataforma.

### Etapa 8 — Cierre y alta

Documentos firmados a `4 Documentos firmados`, expediente completo, estatus activo,
alta operativa en Pomelo.

---

## 5. Catálogo de documentos y generadores

Todos en `generadores/`. Los cuatro que usan template lo toman de `assets/`.

| Documento | Generador | Técnica |
|---|---|---|
| Carátula del contrato de crédito | `generar_contrato.py` | Overlay sobre template |
| PLD Anexo 4, persona moral | `generar_pld.py` | reportlab desde cero |
| PLD Anexo 3, persona física | `generar_pld_pf.py` | reportlab desde cero |
| Formato de beneficiario controlador | `generar_beneficiario.py` | reportlab, flowables |
| Anexo de análisis razonado | `generar_anexo_razonado.py` | reportlab, flowables |
| Adenda obligado solidario PM | `generar_adenda.py` | Overlay sobre template |
| Adenda obligado solidario PF | `generar_adenda_pf.py` | Overlay sobre template |
| Autorización de domiciliación | `generar_domiciliacion.py` | Overlay sobre template |

**Decisiones sobre el Formato de Beneficiario Controlador:** se usa el formato
basado en el CFF (arts. 32-B Ter, Quáter y Quinquies, más Reglas 2.8.22 a 2.8.24
RMF). Se descartó la plantilla alterna basada en LFPIORPI porque su aporte único
—la declaración firmada del cliente sobre conocimiento del beneficiario— ya está
en el formato PLD. Al Formato A se le agregaron dos declaraciones en la sección IV:
que ninguna de las personas identificadas es PEP, y que se puso el aviso de
privacidad a su disposición.

**Aviso de privacidad del cliente:** embebido en el contrato de crédito y en el
formato PLD. No es documento aparte.

**Anexo de análisis razonado:** nueve secciones. Lo firma solo cumplimiento; el
cliente no lo suscribe. Tres conclusiones posibles: identificado por control
efectivo, no identificado, o identificación parcial. La sección VIII de medidas
adoptadas solo aparece en los dos últimos casos.

### 5.1 Calibración de overlays

Fórmula para PDF carta (612 × 792), texto que se asienta sobre una línea rellenable:

```
y_reportlab = 792 - pdfplumber_top + 2.0        # líneas dibujadas
y_reportlab = 792 - pdfplumber_top - size * 0.8  # alineado a una fila de texto
```

Los templates hacen los blancos de dos formas distintas: la adenda de persona moral
y la domiciliación usan **corridas de espacios** con una línea trazada debajo; la
adenda de persona física usa **corridas de guiones bajos** como caracteres. La
segunda se localiza buscando caracteres `_` y agrupando corridas contiguas.

**Verificación:** `pdfplumber` entrelaza el texto sobrepuesto con los espacios del
template y produce extracciones aparentemente rotas (`C E V E R`). No es defecto del
documento. Verificar con `pdftotext`.

---

## 6. Estado del código

```
nea_onboarding/
├── generadores/            ← los ocho, probados
├── assets/                 ← cuatro templates PDF
├── schema_expediente.py    ← estructura, compuertas, matriz de documentos
├── adaptadores.py          ← ocho traductores schema → generador
├── generar_paquete.py      ← orquestador de la etapa 6 + manifiesto
├── extraer_csf.py          ← extractor determinista de la CSF
├── extraer_cotizacion.py   ← extractor determinista de la cotización
├── requirements.txt        ← pypdf, reportlab, pdfplumber
└── ESPECIFICACION.md       ← este archivo
```

**Construido y probado:** los ocho generadores · el schema con nueve compuertas
verificadas una por una · la matriz de documentos verificada en siete escenarios ·
el orquestador de extremo a extremo con el expediente real de RAMSOJ · dos
extractores deterministas.

**Cobertura de la captura:** de 116 campos hoja, la CSF y la cotización llenan 30.
De los 86 restantes, unos 17 son decisión humana por diseño.

| Origen de los pendientes | Campos | Cómo se resuelve |
|---|---|---|
| Documentos del obligado solidario | 21 | Los mismos dos extractores sobre su CSF |
| Acta y poderes del representante | 19 | Modelo, o Syntage `current-powers` |
| Acta constitutiva | 16 | Modelo con juicio |
| Decisión de riesgo | 10 | Humana |
| Cumplimiento | 7 | Humana |
| Captura de ventas | 5 | Manual, etapa 0 |

**No construido:** ingesta y escritura en Drive · database de Notion · el Validador
como llamada a API que llene `observaciones[]` · extractor de identificación oficial
· extractor de acta constitutiva · cliente de Syntage · integración con WeeTrust ·
webhook de Google Chat · alimentación automática del modelo de riesgo.

### 6.1 Modelo de riesgo

Cuatro módulos ponderados: estados de cuenta 27.5%, declaración anual 27.5%, buró
25%, perfil de empresa 20%. Score ≥ 0.7 aprueba, ≥ 0.5 va a comité.

Se corrigieron diez defectos, documentados en la hoja `Correcciones` del archivo.
Los dos más graves compartían patrón: **la ausencia de historial se calificaba como
el peor historial**. Un cliente sin créditos abiertos producía división entre cero y
tumbaba el módulo de buró completo; un `Peor_Edo` de 0 caía al último rango y
recibía −2, la penalización máxima. Para un negocio que coloca flotillas en PyMEs
con expediente delgado, eso sesga contra los clientes que se quieren.

Otros: la degradación elegante no operaba porque el error se propagaba aunque la
bandera fuera 0 · las ponderaciones del módulo de declaración anual sumaban 1.20 y
no 1.00 · las fórmulas de estados de cuenta asumían exactamente tres y dos cuentas ·
`Score_pyme_adj` tenía un acantilado de 2.3 puntos en el umbral · `Exclusion` y
`Comité` eran texto dentro del cálculo ponderado.

**Tabla de Estado**, tres códigos por PIB per cápita y siniestralidad logística
(robo a autotransporte, no criminalidad general — para un emisor de flotillas es lo
que importa):

- Código 1 (peso 1.00): Aguascalientes, Baja California Sur, CDMX, Coahuila,
  Jalisco, Nuevo León, Querétaro, Yucatán
- Código 2 (0.75): Baja California, Chihuahua, Estado de México, Guanajuato, Puebla,
  Quintana Roo, San Luis Potosí, Sonora
- Código 3 (0.50): las dieciséis restantes

**Tabla de Giro**, seis códigos por ciclo de conversión de efectivo. Un transportista
cobra al entregar; una constructora cobra a estimaciones. La proveeduría a gobierno
se dejó **fuera** de la tabla: el ciclo largo a gobierno aplica en cualquier giro, y
como código contaminaría la clasificación de un transportista. Va como variable
aparte, medible con `/insights/government-customers` de Syntage.

Con Syntage, los `Días para Cobrar` y `Días para Pagar` reales del cliente van al
resumen ejecutivo como contraste: el código es el promedio del sector, los días son
del cliente.

---

## 7. Deuda técnica y hallazgos abiertos

### Sobre documentos en producción

**El `Manual GRIT` trae el domicilio viejo** del responsable de datos personales
(Av. de los Poetas 100, C.P. 05600). El correcto es **Calle 3 Picos 65, Polanco V
Sección, Miguel Hidalgo, C.P. 11560, tel. 5521207273**, que es lo que traen los
formatos de producción. El Manual es lo que lee un verificador de la UIF.

**El formato PLD declaraba NO** en "Se obtuvo comprobante conocimiento de existencia
(cliente)" de forma fija, así que todos los expedientes generados afirman por
escrito que falta una constancia que el Anexo 4 exige. Corregido en el generador; los
expedientes ya emitidos siguen mal.

**El Formato A de ACC probablemente está desactualizado.** Declara capital social de
$50,000 con 100 acciones de $500 y un órgano de administración tomados de la
constitutiva de 2017, pero Syntage reporta dos asambleas de **aumento de capital
fijo** (nov 2023 y abr 2024) y un nombramiento de funcionarios en 2024. Conviene
resolverlo antes de que ese formato se firme.

**La adenda de persona moral es sustancialmente menos protectora que la de persona
física:** cinco cláusulas contra nueve. La de persona física trae renuncia expresa a
los beneficios de orden y excusión, solidaridad pasiva fundada en los artículos 1987
a 1989 del Código Civil Federal, y supervivencia de la obligación al fallecimiento.
La de persona moral no trae nada de eso.

### Sobre el proceso

**La credencial del SAT es un requisito del cliente** que no estaba en ningún
diseño. Los datos de Syntage derivados del SAT (declaración anual, CFDI, opinión de
cumplimiento) requieren que el cliente autorice la extracción, y las credenciales se
caen — existen endpoints de `revalidate` precisamente por eso. Necesita consentimiento
propio y una compuerta que verifique vigencia antes de que riesgo dependa de esos
datos. Pedirle a un cliente su CIEC tiene implicaciones distintas a pedirle un PDF.

**`descubre-nea.com` es un dominio de Grit sin landing activa.** Pedir la credencial
del SAT desde una dirección en un dominio sin sitio es el patrón que la gente aprende
a desconfiar. O se levanta la landing, o esas solicitudes salen desde `getnea.com`.

**El INE no tiene capa de texto.** Es puras imágenes, así que la identificación
oficial necesita modelo o el endpoint de WeeTrust — y ese último es mejor porque
valida contra el padrón en lugar de solo leer el plástico.

**Los productos del proceso están mezclados con los insumos** en las carpetas
actuales: el modelo de riesgo y el reporte de buró viven junto a los documentos del
cliente. La estructura nueva lo resuelve con `2 Análisis interno`.

---

## 8. Decisiones pendientes

**Bloquean poco pero conviene cerrarlas:**

- Si el ok de ventas es evento detectable (la aparición de la carpeta) o campo que
  alguien marca. Propuesta: la propia carpeta, para no tener una ventana invisible
  entre que el expediente está listo y alguien se entera
- Nombre de la organización de GitHub de Grit
- Renombrar en Drive `3 Documentos firmados` a `3 Documentos generados`
- Crear la unidad compartida (requiere administrador del Workspace)
- Permitir `api.syntage.com` y `api.sandbox.syntage.com` en los dominios de red
- URL del webhook de Google Chat (va en variable de entorno, no en el código)
- Un cuarto código para la tabla de Estado: dieciséis entidades en el código más
  bajo es la mitad del país
- En el modelo, la variable de ingresos divide entre 12 y la de utilidad entre 6.
  No hay razón aparente para que difieran; si el 6 debía ser 12, la variable
  sobrestima al doble
- Entidad y sector reales de Cever, que hoy están inferidos de los nombres de carpeta
- Si Syntage acepta consultas por persona física con CURP o RFC, para cubrir el
  screening de beneficiarios controladores con el proveedor que ya se paga
- Umbral a partir del cual un expediente se rechaza en lugar de aprobarse con
  monitoreo reforzado, en el supuesto de no identificación del beneficiario
- Si la reclasificación de riesgo PLD la calcula una herramienta o es criterio libre
- Cuánto se conserva la documentación de un expediente rechazado
- Cinco días hábiles para informar cambio de domicilio en la adenda de persona
  física: ese valor lo puse yo, confirmar

---

## 9. Pasos para operar

1. **Crear el repo** y hacer el primer commit del paquete. Es lo único que impide que
   este trabajo se vuelva a perder: el entorno de las sesiones se borra
2. **Instalar y correr una vez:**
   ```
   pip install -r requirements.txt
   python generar_paquete.py out/expediente_RAMSOJ.json ./prueba
   ```
   Si salen los cuatro PDFs de RAMSOJ, funciona
3. **Renombrar la carpeta 3** en Drive
4. **Pedir la unidad compartida** al administrador del Workspace
5. **Para cada cliente nuevo:** correr los dos extractores sobre la CSF y la
   cotización, completar a mano el resto del expediente usando
   `out/expediente_RAMSOJ.json` como plantilla, correr el orquestador, subir la
   salida a `3 Documentos generados`

---

## 10. Ruta de construcción sugerida

En orden de valor por esfuerzo:

1. **Extractor de CSF aplicado al obligado solidario y a los beneficiarios
   controladores.** 21 campos con código ya escrito y probado
2. **Database de Notion** con las etapas y propiedades. No requiere código y da la
   visibilidad que es el propósito original de la plataforma
3. **Lectura y escritura en Drive**: descubrir documentos en `1 Documentos del
   cliente`, escribir en `3 Documentos generados`
4. **El Validador de Expedientes como llamada a API**, con salida en JSON que llene
   `observaciones[]` en lugar de un reporte en markdown que alguien lee. El prompt
   tiene que salir del proyecto de chat a un archivo versionado del repo
5. **Extractor de identificación oficial**, vía modelo o vía WeeTrust
6. **Extractor de acta constitutiva.** El bloque más grande y el único que necesita
   juicio: instrumento, fedatario, capital, estructura accionaria, órgano de
   administración y facultades
7. **Cliente de Syntage.** Orden sugerido: `current-powers`, `shareholders` con
   `relationType=shareholders`, `rpc/actos`, `background-checks`. Los cuatro cambian
   etapas que ya están cerradas
8. **Alimentación automática del modelo de riesgo** desde el schema
9. **Resumen ejecutivo y webhook de Google Chat**
10. **Integración con WeeTrust**

---

## 11. Contexto de las personas

- **Luis Gómez Montijano** — dueño del proceso. Autoriza líneas, dispara la
  generación, da de baja expedientes
- **Marcos Siqueiros Ballesteros** — responsable de cumplimiento PLD. Firma las
  determinaciones de beneficiario controlador y el anexo de análisis razonado.
  Firma también por Nea en el contrato y en las adendas
- **Fernando Caballero** (`fercaballero@descubre-nea.com`) — ventas. Crea las
  carpetas y recolecta documentos

**Sujeto obligado:** Grit Payment Solutions, S.A.P.I. de C.V., operando como Nea /
Nea Card. Actividad vulnerable declarada: emisión y comercialización de tarjetas de
servicio.
