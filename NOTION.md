# Database de Notion — Nea, Expedientes de Clientes

Creada el 3 de agosto de 2026. Es la fuente única de verdad del **estado** de cada
expediente; los archivos viven en Drive (ver ESPECIFICACION.md §2.2).

| Qué | Valor |
|---|---|
| Database | `4a4c00b608cc4356a3774f4136f5e605` |
| Data source (collection) | `1c4078b4-c1c9-48d9-adef-8e77b1914889` |
| URL | https://app.notion.com/p/4a4c00b608cc4356a3774f4136f5e605 |

Nació como página privada de Luis; hay que moverla al teamspace y compartirla con
ventas, finanzas, riesgo y cumplimiento cuando el schema esté aprobado.

## Vistas

- **Kanban por etapa** — board agrupado por `Etapa`
- **Atorados — sin movimiento** — etapas activas (0 a 7) ordenadas por `Último
  movimiento` ascendente. El DSL de vistas no soporta fechas relativas, así que el
  corte de 30 días de la especificación se agrega a mano en la UI de Notion:
  filtro `Último movimiento` → *is before* → *one month ago*
- **Rechazados y bajas** — expedientes fuera del kanban, con su motivo estructurado

## Convenciones

- El título de la página es `RAZÓN SOCIAL — FOLIO`, igual que la carpeta de Drive
- `Etapa` incluye los tres estados terminales (`Activo`, `Rechazado`, `Baja`)
  además de las nueve etapas; `Rechazado` exige `Motivo de rechazo`
- `Obligado solidario` nace vacío a propósito: lo llena riesgo en la etapa 5
- `Último movimiento` es `last_edited_time` automático de Notion
- Registro de ejemplo cargado: RAMSOJ-01, en etapa 6

## Mapeo schema → propiedades

| Propiedad de Notion | Campo del expediente |
|---|---|
| Expediente (title) | `cliente.validado.razon_social` + ` — ` + `folio` |
| Folio | `folio` |
| Grupo | `grupo.acronimo` |
| Tipo de cliente | `tipo_cliente` |
| RFC | `cliente.validado.rfc` |
| Representante legal propuesto / validado | `representante_legal.propuesto.nombre` / `.validado.nombre` |
| Correo / Teléfono del representante | `representante_legal.propuesto.correo` / `.telefono` |
| Línea solicitada / propuesta / autorizada | `credito.solicitada.linea` / `autorizada.linea_propuesta_modelo` / `autorizada.linea` |
| Plazo / Tarjetas | `credito.solicitada.plazo` / `.tarjetas` |
| Domiciliación / Obligado solidario | `flags.domiciliacion` / `flags.obligado_solidario` |
| Riesgo PLD | `riesgo_pld.grado` |
| Observaciones abiertas | conteo de `observaciones[]` con estado `abierta` |
| Firma cumplimiento BC | `cumplimiento.bc_firmado_por` no vacío |
| CSF vigente hasta | `documentos[tipo=csf_cliente].vigente_hasta` |
| Fecha de apertura | `fechas.apertura` |
