# UI kit — Plataforma de onboarding (interno)

Tablero de expedientes de Nea Card: uso interno, 2–3 personas, regulado por LFPIORPI. **La plataforma no autoriza**: no hay ni debe haber un botón de aprobar, autorizar, rechazar o firmar. El CTA de esta app es *entender*.

## Pantallas

| Archivo | Pantalla |
| --- | --- |
| `index.html` | **Tablero** — 5 métricas, tabla de 5 expedientes, aviso de atorados |
| `cliente.html` | **Un cliente · Observaciones** (la pestaña difícil): 6 observaciones, dos de ellas aceptadas con justificación firmada completa |
| `cliente-score.html` | **Un cliente · Score** — score con salvedad, 4 módulos con peso y redistribución, evaluaciones anteriores |

Las tres traen un botón `◐` arriba a la izquierda que alterna claro / oscuro (`data-theme` en `<html>`).

## Portabilidad a Streamlit

Todo el sistema visual vive en **`tokens/onboarding.css`** (en la raíz del design system): variables en `:root`, tema oscuro en `[data-theme="dark"]`, y clases planas con prefijo `neaop-`. No hay framework de JS, no hay rejillas arbitrarias, no hay router ni animaciones: sólo lo que se puede inyectar en Streamlit.

```python
import pathlib, streamlit as st
css = pathlib.Path("onboarding.css").read_text(encoding="utf-8")
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
st.markdown('<span class="neaop-badge neaop-badge--comite"><span class="neaop-badge__glyph">◑</span> Comité</span>', unsafe_allow_html=True)
```

Envuelve el contenido en un contenedor con `class="neaop"` (o pon la clase en `<body>` con un `st.markdown` inicial) para heredar tipografía y color. Las fuentes (Space Grotesk, Roboto) se sirven desde `assets/fonts/` vía `tokens/fonts.css`; si la app no puede servir archivos, cárgalas desde Google Fonts o deja el fallback `system-ui` — el sistema no depende de ellas para funcionar.

Los mismos bloques existen como componentes React en `components/onboarding/` y **emiten exactamente estas clases**, así que no hay dos fuentes de verdad: el CSS manda, React sólo lo envuelve.

## Componentes sueltos

`MetricCard` · `ExpedienteRow` · `EtapaChip` / `EtapaFlow` / `DiasEnEtapa` · `VeredictoBadge` · `SeveridadBadge` / `EstadoObservacion` · `ObservacionCard` (con justificación firmada) · `CampoCopiable` (valor / FALTA / vacío a propósito) · `ModuloBar` (incluida la variante sin datos) · `ScoreHeadline`.

## Cómo se resolvió la tensión central

La salvedad **es** el contenido, así que ninguna vive en un tooltip:

- **Score incompleto**: la salvedad va en una banda ámbar pegada al número, con "3 de los 4 módulos" y "**no es comparable**" en negritas. Los pesos redistribuidos se imprimen módulo por módulo (`27.5% → 36.7%`).
- **"No propone" ≠ $0.00**: la línea propuesta ausente se escribe en cursiva gris con la razón debajo. Ningún valor ausente se rellena con cero.
- **Sin datos ≠ rechazado**: gris con borde punteado y glifo `⌀`; la barra del módulo se dibuja rayada, nunca al 0%.
- **Vacío a propósito ≠ FALTA**: caja punteada gris en cursiva con el motivo, contra caja roja con `FALTA` en mayúsculas y la instrucción de qué conseguir.
- **Aceptada ≠ resuelta**: el estado se distingue, y la justificación se imprime completa (una de las del ejemplo tiene 8 líneas), con firma, fecha y el recordatorio de que el riesgo sigue asumido.
- **Daltonismo**: cada estado se codifica tres veces — color, glifo (`✓ ◑ ✕ ⌀ ○` / `▲ ◆ ●`) y tratamiento de borde o patrón (sólido, doble, punteado, rayado). En escala de grises el tablero sigue siendo legible.

## Crítica de la arquitectura de información

Lo que está bien: el orden tablero → expediente, la banda "qué lo detiene", y que las ocho pestañas separen *procedencia* de datos (derivado del SAT vs. capturado por el operador). Eso no lo tocaría.

Lo que cambiaría, **sin esconder ningún dato**:

1. **Ocho pestañas son dos preguntas mezcladas.** Seis contestan "¿qué sabemos de esta empresa?" (Score, Perfil, Banco y fiscal, Documentos, Historial, Observaciones) y dos son entregables (Resumen ejecutivo, Alta en la base operativa). Propondría dos grupos visibles en la misma barra — *Expediente* (6) y *Salidas* (2) — con un separador, no un menú anidado. Cero pestañas eliminadas.
2. **Score y Observaciones deberían estar contiguas y cruzadas.** El score no se entiende sin las observaciones que lo explican: falta el buró (módulo fuera del promedio) es *la misma cosa* que la observación alta "Sin buró de crédito del acreditado". Añadiría en el módulo sin datos un enlace directo a la observación que lo causa y, en la observación, la mención del módulo afectado — que ya está en el pie.
3. **La primera pantalla del expediente no debería ser Score.** Debería ser un resumen de *qué falta y quién lo debe*, porque es la pregunta 4 del operador y hoy exige recorrer tres pestañas. No una pestaña nueva: la banda "Qué lo detiene" crecida a un bloque con los pendientes del cliente, los documentos por vencer y las observaciones abiertas, arriba de las pestañas y siempre visible. Es reordenar, no resumir.
4. **Historial es una columna, no una pestaña.** "Cuántos días lleva en cada etapa" cabe en el flujo de etapas de la cabecera (ya lo dibujamos así). Liberar esa pestaña baja de 8 a 7 sin perder un dato.
5. **Observaciones necesita orden, no filtro.** Con ~30 por expediente, el filtro por estado obliga a decidir antes de leer. Mejor un orden fijo — severidad alta primero, y dentro de cada severidad las abiertas antes que las aceptadas — con los tres contadores visibles como está en la maqueta. Filtrar oculta; ordenar no.
6. **Resumen ejecutivo: documento, no bloque de código.** Se puede componer en `.neaop-doc` (monoespaciado, 96ch, interlineado 1.7) sin editar ni una palabra del texto generado.

Lo que **no** propondría: consolidar módulos del score en un semáforo, ocultar observaciones de severidad baja, resumir justificaciones, ni añadir una vista "cartera" con tendencias — no hay datos que la sostengan.

## Datos

Todos los nombres, RFC y cifras vienen del anexo del brief y son inventados. Los expedientes se maquetaron **a medias a propósito**: módulos sin datos, observaciones abiertas y campos faltantes son el estado normal, no el caso de error.
