# SIMON — Funcionalidades avanzadas (guía operativa)

Mejoras incorporadas sobre la base (FASES 0–6). Todas están en producción en
https://192.168.50.54/. Esta guía resume **qué hacen** y **cómo operarlas**.

| Funcionalidad | Migración | Capas tocadas |
|---|---|---|
| Interfaces SNMP (IF-MIB) | 0004 | worker · API · frontend |
| Dependencias padre→hijo | 0005 | BD · worker · API · frontend |
| Reportes de disponibilidad (SLA) | — | API · frontend |
| Mapa de sedes | — | frontend |
| Bitácora de auditoría | 0006 | BD · API · frontend |
| Interfaces Fase 2 (histórico + alertas) | 0007 | BD · worker · API · frontend |

---

## 1. Interfaces SNMP (IF-MIB)

Monitorea los puertos de equipos SNMP: estado oper/admin, **tráfico in/out en Mbps**
(calculado por delta de contadores HC de 64 bits), **utilización %**, errores y velocidad.

**Cómo activarlo en un equipo:** en *Recursos → Editar*, en **Parámetros (JSON)** añade
`"interfaces": true`. En el siguiente ciclo el worker recorre la IF-MIB y muestra la sección
**"Interfaces"** en el detalle del recurso.

- Solo lista interfaces **físicas y agregados** (ethernet, port-channel); descarta VLANs y loopback.
- El throughput requiere 2 ciclos para el primer dato (y tras reiniciar el worker).

## 2. Dependencias padre→hijo (anti-tormenta de alertas)

Evita 30 alertas cuando cae el enlace/firewall de una sede: solo alerta la **causa raíz**.

**Cómo modelarlo:** en *Recursos → Editar*, campo **"Depende de"** → elige el recurso aguas
arriba. Encadena según tu topología, p. ej.:

```
servidores / switches  →  switch core  →  firewall  →  enlace WAN/Starlink
```

Si un **ancestro** está `down`, el worker **suprime** la incidencia y la notificación del hijo
(lo registra como `dependencia_caida`; en el detalle aparece un aviso "alertas silenciadas").
La API rechaza ciclos y autodependencias.

## 3. Reportes de disponibilidad (SLA)

Pantalla **"Reportes"**: disponibilidad por recurso en **24h / 7d / 30d**, ordenado peor-primero,
con KPIs (promedio, incidencias) y **exportar CSV**.

`disponibilidad = (operativo + degradado) / chequeos evaluables` (excluye mantenimiento y sin-dato).

## 4. Mapa de sedes

Pantalla **"Mapa"**: contorno de Colombia (SVG embebido, **funciona sin internet**) con un
marcador por sede, **coloreado por el peor estado** de sus recursos y dimensionado por cantidad.
Requiere latitud/longitud en *Sitios* (los que no las tengan se listan aparte).

## 5. Bitácora de auditoría (solo admin)

Pantalla **"Auditoría"**: registra automáticamente **quién** hizo **qué** y **cuándo**:
crear/actualizar/eliminar de las entidades de gestión (con **diff antes/después**), y logins
(exitosos y fallidos). Filtros por acción, entidad y texto. El actor queda desnormalizado
(`actor_email`) para sobrevivir al borrado del usuario.

> Las escrituras del worker (Python) no generan ruido; solo se auditan las acciones por la API.

## 6. Interfaces Fase 2 — histórico y alertas por puerto

Sobre la funcionalidad 1:

- **Histórico/gráficas:** en el detalle, haz clic en una fila de interfaz para desplegar las
  **gráficas de Entrada/Salida (Mbps)** del puerto (rango 1h/24h/7d). Se guarda en
  `interfaces_historico` (solo puertos oper-up) con **retención de 7 días**.
- **Alerta por puerto:** marca la casilla **"Monitorear"** en los puertos críticos (uplinks/WAN).
  Cuando un puerto monitoreado pasa a **oper-down**, el worker **abre una incidencia**
  ("puerto X caído") y **notifica**; al recuperarse, la **cierra**. Respeta mantenimiento y la
  supresión por dependencia.

---

## Despliegue / operación

- Repo en el servidor: `/opt/monitoreo`. Scripts en `infra/deploy/` (numerados por hito).
- Actualizar: `git pull` + aplicar migración pendiente (`psql -f db/migrations/NNNN_*.up.sql`) +
  `php artisan optimize:clear` (API) + `ng build` (frontend) + `systemctl restart monitoreo-worker`.
- Verificación integral (solo lectura): `infra/deploy/verify_consolidado.sh`.
- Secretos del servidor en `/root/monitoreo-secrets.env` (NO en el repo).
