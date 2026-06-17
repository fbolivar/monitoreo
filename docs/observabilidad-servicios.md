# Observabilidad de servicios — Guía de uso

La pantalla **Servicios** convierte el monitoreo de infraestructura ("¿el servidor
está UP?") en **observabilidad de negocio** ("¿por qué el usuario percibe lentitud,
dónde está el cuello de botella y qué decisión tomar?").

## Qué es un "servicio" (transacción)
Un **servicio** es una **transacción/journey** que tú defines: una cadena ordenada de
componentes (p. ej. **Web → API Gateway → Catálogo → Base de Datos**), donde cada salto
se enlaza a un **recurso que SIMON ya monitorea**. SIMON toma de cada recurso su
latencia y su estado, y los **correlaciona**.

> No es automático ni muestra "todo": muestra **los journeys que tú defines**, sanos o
> con afectación. El Dashboard muestra los 47 recursos; Servicios es la capa de negocio
> encima (tus 5–10 servicios críticos).

## Cómo leer la pantalla
- **Resumen (arriba):** cuántos servicios hay, cuántos **con afectación**, cuántos sanos.
  La lista va **de mayor a menor afectación** (lo urgente, primero).
- **Acción recomendada:** la decisión concreta para ese servicio (atender / optimizar / vigilar).
- **Experiencia del usuario:** la latencia del **salto de entrada** vs tu **objetivo**.
  Verde si está dentro; el flag distingue *"experiencia lenta"* de *"dependencia degradada"*.
- **Correlación de servicios:** el flujo dibujado; el salto con problema se marca como **causa raíz**.
- **Latencia por salto (waterfall):** dónde se va el tiempo. Los **equipos SNMP**
  (servidores/switches) muestran **salud**, no latencia (su latencia es tiempo de sondeo,
  no de servicio); los de respuesta real (web, firewall API, ping) muestran latencia.
- **Causa raíz:** el componente que más afecta + el motivo de su incidencia (si la hay).
- **Impacto al negocio:** la nota que escribiste (conversión, ventas, operación…).

## Cómo crear una transacción (paso a paso)
1. Entra a **Servicios** → botón **"+ Nueva transacción"** (rol admin/operador).
2. **Nombre:** el journey ("Pago de servicios en línea").
3. **Objetivo de experiencia (ms):** el SLA de la página/servicio (p. ej. 2000 = 2 s).
   Si la latencia de entrada lo supera → "alto impacto".
4. **Impacto al negocio:** una frase ("Mayor abandono de carrito; afecta ventas").
5. **Cadena de la transacción:** agrega un componente por salto, en orden:
   - **Nombre** del salto ("Web", "Catálogo", "Base de Datos").
   - **Tipo** (web/api/gateway/cache/db/externo/servicio) — solo es el ícono.
   - **Recurso** que aporta su latencia/estado (elige uno de los monitoreados).
   - **Umbral ms** (opcional): marca el salto si lo supera.
6. **Guardar.** La transacción aparece en la lista con su análisis en vivo.

### Consejos para que sea fiel
- El **primer salto** debería ser de **respuesta real** (un sitio web, el firewall por API,
  o un ping) para que la "experiencia del usuario" sea significativa.
- Los **servidores/switches** (SNMP) ponlos como saltos de **salud** en la cadena: cuando
  se degraden (CPU, disco, sin respuesta), aparecerán como **causa raíz** del servicio.

## Cómo se toma una decisión (ejemplo real)
*"Servicios internos · Sede Central"* → la experiencia es rápida (661 ms) **pero** está en
**alto impacto** porque un **servidor tiene el disco al 98.6%**. La acción recomendada:
**liberar/ampliar ese disco** antes de que se caiga. El monitoreo diría "UP"; la
observabilidad te dice *qué* arreglar y *por qué*.

## Niveles de objetivo (SLA) sugeridos
El `objetivo_ms` marca cuándo la experiencia de entrada es "lenta". Criterio usado:

| Tipo de servicio | Objetivo |
|---|---|
| Transaccional (pagos) | 2000 ms |
| Portales ciudadanos (web pública de consulta) | 3000 ms |
| Servicios internos / conectividad (infra) | 2500 ms |
| App de gestión interna | 2500 ms |

Ajústalos por servicio según tu compromiso real con el usuario (editar la transacción).

## Camino B (futuro): observabilidad "real"
Lo anterior es observabilidad **desde afuera** con lo que SIMON ya mide. Para **experiencia
real del usuario (RUM)** y **trazas distribuidas** de las apps del cliente, se añade un
endpoint de ingesta (`POST /ingest/rum` y `/ingest/span`) + un beacon JS/OTel en la app.
Pendiente de decisión.
