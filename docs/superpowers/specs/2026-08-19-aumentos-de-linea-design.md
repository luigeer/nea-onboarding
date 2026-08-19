# Aumentos de línea de crédito para clientes existentes

Fecha: 19 de agosto de 2026

## El problema

La plataforma abre expedientes de clientes nuevos y los lleva hasta la firma del
contrato. No sabe nada de lo que pasa después. Cuando un cliente que ya opera
pide más línea, ese proceso vive fuera del sistema: no hay dónde registrar la
solicitud, ni con qué evaluarla, ni cómo dejar constancia de quién la autorizó.

Un aumento **no es un contrato nuevo**. El cliente no firma nada. Por eso las
nueve compuertas de generación —que existen para que el contrato sea exigible:
facultad para suscribir títulos de crédito, poder mancomunado con cofirmantes,
determinación del beneficiario controlador firmada por cumplimiento— no aplican.
Lo que sí hace falta es lo que informa la decisión de crédito.

Y hay un hecho que condiciona el diseño: **la mayoría de los clientes que operan
hoy son anteriores al sistema y no tienen expediente aquí.** Al revisar la base
solo hay tres folios —DEMO-01, DEMO-02, DEMO-03—. Un aumento tiene que poder
arrancar para un cliente que la plataforma nunca vio.

## Qué se pide en un aumento

1. Syntage actualizado
2. Buró de crédito actualizado — se genera para cada aumento
3. Uso de la tarjeta Nea: transacciones, depósitos, estados de cuenta, comisiones
4. Cotización de la solicitud
5. Estados de cuenta bancarios **solo por excepción**: cuando el incremento
   supera $150,000, o cuando el operador decide pedirlos caso por caso
6. Evidencia de la autorización: captura del correo o del WhatsApp
7. Si se aprueba un monto **menor** al solicitado: cotización nueva con el monto
   aprobado, además de la evidencia

No se pide acta constitutiva, ni poderes, ni estructura accionaria: esas
validaciones se dieron por resueltas al abrir la cuenta.

## Decisiones de arquitectura

### Se extiende el expediente; no se crea un registro paralelo

Un aumento vive en el expediente del cliente. La alternativa —una tabla aparte
de aumentos— duplicaría lo que el expediente ya resuelve (documentos, vigencias,
procedencia, compuertas) y crearía el problema que `OPERAR.md` advierte por
escrito: dos lugares que responden por el mismo cliente y que pueden
contradecirse. Cuando dos tableros no coinciden, no se cree ninguno.

### Las compuertas de generación no se tocan

Se agregan dos compuertas nuevas, propias del aumento. Las nueve de
`compuertas_generacion` quedan intactas y siguen sirviendo a los clientes nuevos.
Ningún cambio de este proyecto debe alterar el comportamiento de la ruta de
originación.

### El modelo de originación no se toca

Se agrega `evaluar_aumento()`, con su propia tabla de pesos y su propia cadena de
versión. `evaluar()` queda igual. Un score de aumento no es comparable contra uno
de originación porque se calcula con módulos distintos, y la versión guardada es
lo que permite saberlo después.

## El esquema

### `historial_aumentos`

Lista nueva en el expediente, una entrada por ronda:

```python
{
    "fecha_solicitud": None,
    "linea_previa": None,          # credito.autorizada.linea antes de esta ronda
    "monto_solicitado": None,
    "estados_cuenta_excepcion": None,   # {motivo, decidida_por, fecha} si se piden
                                        # sin que el incremento llegue al umbral
    "riesgo": {"score": None, "version": None, "fecha_evaluacion": None},
    "monto_aprobado": None,
    "fecha_decision": None,
    "autorizado_por": None,        # nombre, tomado de la evidencia
    "estado": "abierta",           # abierta | cerrada
}
```

`credito.autorizada.linea` sigue siendo la línea vigente: se sobreescribe al
cerrar cada ronda. El histórico completo queda aquí.

### Documentos de la ronda

No se duplican dentro de `historial_aumentos`. Se agregan al arreglo `documentos`
que ya existe, con un campo nuevo:

- `ronda_aumento`: índice de la ronda en `historial_aumentos`, o `None` para los
  documentos de la apertura original.

Así una ronda futura puede preguntar qué papel entró en *esta* vuelta sin que
haya una segunda lista de documentos con reglas de vigencia propias.

### `uso_plataforma`

El resultado de leer el Excel se guarda en el expediente; no se recalcula en cada
comando:

```python
"uso_plataforma": {
    "ronda_aumento": None,      # a qué ronda corresponde esta lectura
    "archivo": None,            # nombre del Excel del que salió
    "fecha_lectura": None,
    "periodo": {"desde": None, "hasta": None},
    "gasto_total": None,
    "gasto_por_mes": {},
    "usuarios": None, "tarjetas": None,
    "comercios": None, "concentracion_mayor": None,
    "comisiones_por_tipo": {},
    "ciclos": [],               # por corte: exigible, acreditado al vencer,
                                # faltante, dias de atraso, dias de holgura
    "atrasos": {"cuantos": None, "peor_dias": None, "monto_mayor": None},
}
```

`aumento riesgo` lee de aquí. Guardarlo en vez de recalcularlo deja constancia de
con qué datos se calculó el score, que es la misma razón por la que el modelo
guarda su `VERSION`.

### La línea vigente de un cliente heredado

`linea_previa` se toma de `credito.autorizada.linea`. Para un cliente heredado ese
campo está vacío: la plataforma nunca vio su alta. Y de esa cifra dependen dos
cosas —la regla de los $150,000 y la variable de utilización promedio—, así que no
puede quedar en blanco.

Por eso `aumento nuevo` acepta `--linea-actual`. Es obligatoria cuando
`credito.autorizada.linea` está vacía, y se rechaza cuando ya tiene valor: si el
sistema ya sabe la línea, no se teclea otra vez. Al usarla se llena también
`credito.autorizada.linea`, de modo que la segunda ronda del mismo cliente ya no
la pide.

### Etapa nueva: `operando`

`ETAPAS` pasa a ser:

```
apertura → validacion → riesgo → generacion → firma → cerrado → operando
```

`operando` significa: ya es cliente, no está en el pipeline de apertura de
cuentas nuevas. No hereda el SLA de 3 días de `apertura` ni la marca `!` de
atorado. Un expediente puede vivir ahí de forma permanente, con o sin ronda
abierta. Es la etapa con la que se abre un cliente heredado.

## El lector de uso de plataforma

Archivo nuevo: `uso_plataforma.py`. Mismo patrón que `bbva.py`.

Entrada: el libro de Excel que sale de consultar la base de datos de la
plataforma, con cuatro pestañas:

| Pestaña | Columnas |
|---|---|
| Transacciones | Fecha Aprobación, Fecha Creación, Merchant Name, Usuario, Últimos 4 dígitos, Monto |
| Depósitos | Empresa, Concepto, Emisor, Código de rastreo, Monto, Fecha de operación |
| Estado de Cuenta | ID, Empresa, Fecha de inicio, Fecha de corte, Fecha de pago, Saldo al inicio, Saldo al corte, ¿Facturado? |
| Comisiones | Fecha de transacción, Importe, IVA, Account statement id, Empresa, Nombre de la comisión |

Notas de formato verificadas contra un export real:

- Las fechas de Depósitos, Estado de Cuenta y Comisiones vienen como **texto** en
  formato `"Aug. 10, 2026"` o `"July 31, 2026, 11:59 p.m."`, con `midnight` y
  `noon` como valores posibles de hora. Las de Transacciones vienen como ISO.
- Los encabezados llegan con los acentos corrompidos: donde va la vocal acentuada
  aparece un carácter de reemplazo, así que "Código de rastreo" y "Nombre de la
  comisión" no coinciden por igualdad literal. El lector reconoce la columna por
  las letras sin acento y nunca depende del acento.

Si falta una pestaña o una columna no calza, el mensaje es claro y el código de
salida distinto de cero. Nunca una excepción cruda ni un `None` silencioso.

### Lo que calcula

- Gasto total y por mes
- Comercios distintos y concentración del mayor
- Usuarios y tarjetas distintas
- Comisiones agrupadas por tipo
- **Atrasos, derivados** (ver abajo)

### Derivación del atraso

El cliente está obligado a pagar el **saldo completo** al corte; si no, se le
bloquea la transaccionabilidad. No hay pago mínimo. Por lo tanto:

> Para cada estado de cuenta, el exigible es `Saldo al corte`. Se suman los
> depósitos acreditados hasta la `Fecha de pago`, descontando lo que ya estaba
> comprometido con los cortes anteriores. Si lo acreditado no cubre el exigible,
> hay atraso: el faltante es el monto, y los días son los que pasaron hasta que
> un depósito posterior lo cubrió.

Esto entrega las tres dimensiones sin captura manual: cuántos atrasos, por
cuánto monto, y de cuántos días.

Verificado contra un export real de un cliente (2 ciclos): junio cubierto 1 día
antes del vencimiento, julio cubierto 4 días antes, cero atrasos.

## El módulo de riesgo nuevo

### Variables de `uso_plataforma`

| Variable | Peso | Fuente |
|---|---|---|
| Atrasos | 0.45 | Derivado del cruce cortes / depósitos |
| Alineación al giro | 0.25 | Comercios clasificados, contra el giro del cliente |
| Usuarios activos | 0.15 | Usuarios y tarjetas distintas |
| Utilización promedio | 0.15 | Gasto mensual promedio contra la línea vigente |

**Atrasos.** Escalón por el atraso más grave del periodo. Un atraso de uno o dos
días suele ser error operativo; patear el pago y generar moratorios es otra cosa,
y la escala tiene que distinguirlas.

| Atraso más grave | Puntaje |
|---|---|
| Sin atrasos | 1.00 |
| 1 a 2 días | 0.85 |
| 3 a 7 días | 0.60 |
| 8 a 29 días | 0.35 |
| 30 días o más | 0.10 |

Dos ajustes sobre ese puntaje, con piso en 0.10 y techo en 0.95 —un ciclo con
atraso nunca puntúa igual que uno sin atraso—:

- **Reincidencia:** −0.10 por cada ciclo con atraso además del primero.
- **Proporción:** si el faltante al vencimiento fue menos del 5% del exigible,
  +0.10 (es un descuadre, no una falta de fondos); si fue más del 50%, −0.10.
  Deber $500 no es deber $50,000.

**Alineación al giro.** Se sugiere por palabra clave y el operador confirma, mismo
principio que `giros.py` ya establece: una coincidencia de texto no sustituye un
juicio de negocio. Los comercios sin clasificar se reportan, no se puntúan. Los
**retiros de efectivo** cuentan como desalineación: en una tarjeta de flotilla el
efectivo no es gasto controlado.

**Usuarios activos.** Más usuarios puntúa mejor. El objetivo de negocio es estar
más permeados en la empresa; un solo usuario es concentración.

**Utilización promedio.** Gasto mensual promedio contra la línea vigente.

### Lo que no entra al score

Las **comisiones por financiamiento** son la mensualidad del producto, no una
señal de comportamiento. En el export verificado, tres de las cuatro caen
exactamente en el día de inicio del ciclo y el monto subió de $1,000 a $1,500.
Es el mismo concepto que el expediente ya guarda como
`credito.autorizada.mensualidad`. Se reportan como contexto y sirven para
verificar que la mensualidad cobrada coincida con la cotizada.

### Pesos por módulo en `evaluar_aumento()`

| Módulo | Peso |
|---|---|
| uso_plataforma | 27.5% |
| declaración anual (Syntage) | 22.5% |
| buró | 22.5% |
| estados de cuenta | 15.0% |
| perfil de empresa | 12.5% |

Una sola tabla. En el caso normal —sin estados de cuenta, porque no se piden— ese
módulo se cae y los otros cuatro se renormalizan entre ellos con el mecanismo que
el modelo ya tiene y ya está probado: uso 32.4%, declaración 26.5%, buró 26.5%,
perfil 14.7%. Cuando sí se piden, entran los cinco según la tabla. **No hay
lógica especial para los dos casos.**

Umbrales sin cambio: 0.70 aprueba, 0.50 va a comité. Cadena de versión propia,
`2026.08-aumentos`, porque el score no es comparable contra uno de originación.

## Las dos compuertas

### `compuertas_riesgo_aumento(exp)`

Lo que hace falta antes de correr el modelo:

- Syntage actualizado: una extracción guardada para el folio con fecha posterior a
  la `fecha_solicitud` de la ronda. Syntage **no** entra al expediente como
  documento —`syntage.guardar_crudo()` deja los recursos en su propia tabla, por
  folio—, así que esta compuerta consulta esa extracción, no el arreglo
  `documentos`.
- Buró actualizado: documento de tipo `buro` con `fecha_emision` posterior a la
  `fecha_solicitud`. Este sí es un documento del expediente.
- Uso de la plataforma capturado: el bloque `uso_plataforma` existe y su
  `ronda_aumento` es la de la ronda abierta.
- Estados de cuenta bancarios **solo si** el incremento (`monto_solicitado -
  linea_previa`) supera $150,000, **o** si `estados_cuenta_excepcion` está lleno.
  En cualquiera de los dos casos: 3 estados frescos. Si no aplica ninguno, la
  compuerta de banco no se evalúa.

### `compuertas_cierre_aumento(exp)`

Lo que hace falta para cerrar la ronda una vez decidida:

- Cotización de la solicitud
- Evidencia de la autorización (captura de correo o WhatsApp)
- Si `monto_aprobado < monto_solicitado`: cotización nueva con el monto aprobado
- `autorizado_por` con nombre

## Los comandos

```bash
nea.py nuevo <csf.pdf> --heredado          # solo la primera vez, si no tiene folio
nea.py aumento nuevo <folio> <monto> [--linea-actual <monto>]
nea.py uso <folio> <excel.xlsx>
nea.py aumento estado <folio>
nea.py aumento riesgo <folio>
nea.py aumento cerrar <folio> --aprobado <monto> --evidencia <ruta> \
                              [--cotizacion-aprobada <ruta>]
nea.py aumento tablero
```

`--heredado` abre el expediente en etapa `operando` en vez de `apertura`. Sin la
bandera, `nuevo` se comporta exactamente como hoy. La validación que ya existe se
conserva en los dos casos: si el contribuyente no está ACTIVO en su CSF, no se
abre expediente.

La CSF para abrir un cliente heredado se descarga a mano desde la plataforma de
Syntage. El catálogo `RECURSOS` de `syntage.py` no expone hoy ninguna ruta que
entregue la constancia como PDF; si existe, cablearla es trabajo aparte de este
diseño.

`aumento riesgo` muestra el score y, **por separado**, el resumen de
comportamiento de uso y la verificación de mensualidad. Lo que no entra al número
se reporta como contexto, igual que el resumen ejecutivo ya separa lo que el
score no captura.

`aumento tablero` lista las rondas abiertas —folio, monto solicitado, días desde
la solicitud— con su columna de qué las detiene, corriendo las dos compuertas
nuevas. Es un tablero aparte del de onboarding, para no mezclar clientes que
operan con prospectos.

## Pruebas

La compuerta del proyecto es `python tests/todas.py` y el veredicto es el código
de salida. Todo entra por TDD: primero la prueba que describe el comportamiento.

Archivos nuevos, que `todas.py` recoge solo:

- `tests/test_uso_plataforma.py` — lectura de las cuatro pestañas, tolerancia a
  los encabezados con acentos rotos, parseo de las fechas en texto, y la
  derivación de atrasos con casos: sin atraso, atraso de 1 día, atraso largo,
  atraso parcial, y reincidencia
- `tests/test_compuertas_aumento.py` — las dos compuertas, incluyendo que la de
  banco **no** se evalúe cuando el incremento no llega al umbral y no hay
  excepción, y que sí lo haga en ambos casos en que aplica
- `tests/test_modelo_aumento.py` — `evaluar_aumento()`, la renormalización cuando
  falta el módulo de estados de cuenta, y que la escala de atrasos distinga el
  error operativo del atraso sostenido

Además, una prueba de que `evaluar()` y `compuertas_generacion` **no cambiaron**
de comportamiento: es la garantía de que la ruta de originación sigue intacta.

## Fuera de alcance

- Conectar la base de datos de la plataforma directamente. Hoy los datos salen
  por consulta y llegan como Excel; el lector asume ese archivo.
- Descargar la CSF desde la API de Syntage.
- Un comando de autorización. Igual que en originación, la decisión se toma
  fuera del sistema y aquí se registra con su evidencia.
- Cambiar el front. Este proyecto es de línea de comandos.
