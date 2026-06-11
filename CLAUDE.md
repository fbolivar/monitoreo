# CLAUDE.md — SIMON · Sistema Integral de Monitoreo

> Nombre del producto: **SIMON** ("Sistema Integral de Monitoreo"), con identidad
> corporativa de **Parques Nacionales Naturales de Colombia** (tema claro verde,
> logo, favicon, tipografía GOV.CO Montserrat/Work Sans). Antes "Sistema de
> Monitoreo de Disponibilidad de TI".

## Objetivo del proyecto
Aplicación web para monitorear en tiempo casi-real la DISPONIBILIDAD y el
estado de salud de los recursos de tecnología de la entidad. Debe detectar
caídas, degradaciones y recuperaciones, registrar histórico, y notificar.

## Recursos a monitorear (tipos)
- Firewalls (FortiGate)
- Servidores (físicos y virtuales)
- Switches de red (LAN)
- Esquemas de almacenamiento NAS
- Switches de fibra (SAN / Fibre Channel)
- UPS (sistemas de respaldo de energía)
- Enlaces satelitales Starlink
- Enlaces de fibra óptica (WAN)
- Sitios web (internos y públicos)

## Stack y separación de responsabilidades (NO mezclar capas)
- **Frontend:** Angular (última LTS). SPA. Consume la API PHP por REST y refresca
  el estado por **polling** al API (no Supabase Realtime). NO accede a la BD directo.
- **API:** PHP con Laravel. Expone REST. Responsable de: CRUD de recursos,
  autenticación/autorización, configuración, umbrales, reportes. Conecta a
  PostgreSQL vía PDO/Eloquent. **Autenticación LOCAL**: emite y valida su propio JWT
  (HS256, AUTH_JWT_SECRET); contraseñas bcrypt en `perfiles`. (Sin Supabase.)

> **Cambio de arquitectura (2026-06-10):** se descartó Supabase. La autenticación es
> local (JWT propio de la API, contraseñas en `perfiles.password_hash`) y el "en vivo"
> del dashboard es por polling. La BD es el Postgres del servidor, no Supabase.
- **Workers de monitoreo:** Python. Procesos headless que leen los recursos
  activos, ejecutan los chequeos según su intervalo, y escriben resultados en
  la BD (chequeos, métricas, incidencias). Usan APScheduler para la
  planificación. NO exponen API pública (solo un endpoint /health opcional).
- **Base de datos:** PostgreSQL gestionado por Supabase en la fase inicial.
  Diseñar TODO (esquema, queries, migraciones) para ser portable a un Postgres
  estándar en servidor virtual después. NO usar features propietarias de
  Supabase que no existan en Postgres puro, salvo Auth y Realtime que se
  aíslan en su propia capa.

## Estructura del repositorio (monorepo)
```
monitoreo/
├── frontend/   # SPA Angular (LTS). REST + Supabase Realtime. NO accede a la BD.
├── api/        # REST PHP/Laravel. CRUD, auth (valida JWT Supabase), umbrales, reportes.
├── monitor/    # Workers Python + APScheduler. Probes → chequeos, metricas, incidencias.
├── db/         # Esquema PostgreSQL: migrations/ (NNNN_*.up.sql / .down.sql) + seeds/.
├── infra/      # docker-compose (Postgres local dev) + .env + initdb/.
└── docs/       # Documentación, incl. modelo-datos.md (diagrama ER + flujo).
```

## Catálogo de estados (aprobado 2026-06-10)
- **recurso / chequeo:** `up` (operativo) · `degraded` (responde pero fuera de umbral / warning) ·
  `down` (caído / critical) · `unknown` (sin datos o no evaluable) · `maintenance` (ventana de mantenimiento, alertas silenciadas).
- **incidencia:** `abierta` · `reconocida` · `resuelta`.
- **severidad:** `info` · `warning` · `critical`.
- **notificación:** `pendiente` · `enviada` · `fallida`.

## Cifrado de secretos (aprobado)
- Parámetros NO sensibles en `parametros`/`config` (jsonb en claro).
- Secretos (community SNMP, api_key, password, tokens) en columna `secretos` (bytea),
  cifrados con **pgcrypto `pgp_sym_encrypt` (AES-256)** vía `cifrar_secreto()` / `descifrar_secreto()`.
- La clave maestra `APP_CRYPTO_KEY` vive en la API (Laravel `.env`), **NUNCA en la BD**.

## Política de retención escalonada (aprobada)
| Dato | Tabla | Retención |
|---|---|---|
| Chequeos crudos | `chequeos` | 30 días |
| Métricas crudas | `metricas` (particionada por mes) | 15 días |
| Agregado horario | `metricas_rollup_horario` | 90 días |
| Agregado diario | `metricas_rollup_diario` | 730 días |
| Incidencias | `incidencias` | indefinido (histórico) |

Funciones SQL: `fn_rollup_metricas_horario`, `fn_rollup_metricas_diario`, `fn_purgar_datos`,
`fn_crear_particion_metricas`, `fn_drop_particiones_metricas`. Las invoca el worker (APScheduler) o `pg_cron` donde exista.

## Estado de fases
- ✅ FASE 0 (estructura + Postgres local Docker) y FASE 1 (modelo de datos) — completas y aprobadas (2026-06-10).
- ✅ FASE 2 (API Laravel 11 en /api) — completa y aprobada (2026-06-10). Solo gestión:
  auth por JWT de Supabase, CRUD de los 6 recursos de configuración, lectura con filtros
  de chequeos/metricas/incidencias, autorización por rol (viewer/operador/admin),
  cifrado transparente de secretos vía pgcrypto, tests de endpoints críticos.
  Incidencias quedan en solo-lectura hasta los workers. Se añadió /api/usuarios (solo admin).
- ✅ FASE 3 (Workers Python en /monitor) — completa y aprobada (2026-06-10). Probes
  ICMP / HTTP-HTTPS (incl. días de cert SSL) / TCP; APScheduler con un job por recurso;
  evaluación de estado por umbrales (up/degraded/down/unknown); máquina de incidencias
  con anti-flapping (down inmediato, degraded respeta duracion_segundos); respeto de
  mantenimientos; secretos descifrados vía pgcrypto igual que la API; tareas de
  rollup/purga/particiones. Recursos SNMP/Starlink cubiertos por ICMP mientras tanto.
- ✅ FASE 3b (probes nativos, uno por uno):
  - ✅ Paso 1 SNMP v2c/v3 (servidor/switch_lan/switch_san/nas/ups, UPS-MIB) — aprobado (2026-06-10).
  - ✅ Paso 2 Starlink gRPC con fallback ICMP — aprobado (2026-06-10).
  - ✅ Paso 3 FortiGate API REST (firewalls; clúster HA como un recurso; estado
    operativo/degradado/caído + detección de failover) — aprobado (2026-06-10).
  Nota: la E/S de red de los 3 probes (pysnmp/grpcio+yagrc/httpx) NO se validó
  contra equipos reales (solo compileall + runtime de funciones puras). La lógica HA
  de FortiGate se propuso (CLAUDE.md no la definía en detalle).
- ✅ FASE 4 (Frontend Angular 20 en /frontend) — completa, validada con `ng build` (sin errores):
  - Base: Supabase Auth (login/sesión/guard/interceptor JWT), capa de servicios a la API,
    layout NOC denso, autorización por rol (viewer solo lectura), tema oscuro con semáforo.
  - Pantalla 1 Dashboard: semáforo agrupado por sitio y tipo + Supabase Realtime (estado en vivo).
  - Pantalla 2 Detalle de recurso: gráficas SVG históricas por métrica (rango 1h/24h/7d),
    último chequeo, línea de tiempo de incidencias con duración.
  - Pantalla 3 Gestión de recursos: CRUD completo (parámetros + secretos write-only), gated por rol.
  - Pantalla 4 Incidencias: activas/histórico, severidad, duración.
  - Pantalla 5 Configuración: umbrales, mantenimientos y canales (CRUD, gated por rol).
  Stack: Angular 20.3 standalone + signals; @supabase/supabase-js. Node 24.13 no soporta Angular 22
  (requiere ≥24.15), por eso se fijó Angular 20. NO ejecutado contra API/Supabase reales (solo build).
- ✅ FASE 5 (Motor de notificaciones en /monitor) — completa, compile + runtime de lógica pura:
  al abrir/cerrar incidencia (y en escalamientos de severidad) notifica por canales activos
  (email SMTP / Telegram / webhook). Deduplicación por (incidencia,canal,evento) + anti-flapping
  (cooldown de 'apertura' por recurso). Escalamiento por severidad: `config.min_severidad` por canal
  + evento de escalada al subir severidad. Respeto de mantenimiento (heredado del runner). Cada
  envío se registra en `notificaciones` (enviada/fallida/intentos/error) con job de reintentos.
  E/S de red (SMTP/httpx) NO validada contra servicios reales (solo compileall + funciones puras).

- ✅ FASE 6 (Despliegue en servidor 192.168.50.54, Debian 12) — en PRODUCCIÓN. nginx
  (HTTPS autofirmado + redirección HTTP→443, SPA en / y /api → php8.2-fpm), worker como
  servicio systemd, ufw, backups diarios (pg_dump, ~02:30). Auth LOCAL (JWT propio, sin
  Supabase) y "en vivo" del dashboard por polling. Monitorea 3 equipos reales: FortiGate-Principal
  (HA), SW-CORE-01 (Dell OS9), PNNCSRVNCFHV2 (Windows). Notificaciones por correo (Gmail/Workspace)
  ACTIVAS. Rebranding a SIMON / Parques Nacionales. Pantallas añadidas: Sitios (CRUD),
  reconocer/resolver incidencias.

- ✅ MEJORAS DE OPERACIÓN (roadmap de mercado, 2026-06-11) — todas en producción y verificadas:
  - **Interfaces SNMP (IF-MIB)** [migr. 0004]: snapshot por puerto (estado oper/admin, Mbps in/out
    por delta de contadores HC64, util %, errores, velocidad). Opt-in `parametros.interfaces=true`;
    filtra a tipos físicos (ethernet/lag). Tabla `interfaces`; GET /recursos/{id}/interfaces; sección
    "Interfaces" en el detalle.
  - **Dependencias padre→hijo (anti-tormenta)** [migr. 0005]: `recursos.depende_de_id` (self-FK).
    Si un ancestro (CTE recursivo) está down, el worker suprime incidencia+notificación del hijo
    (registra `dependencia_caida`). API valida ciclos/autodependencia. UI: selector "Depende de".
  - **Mapa + reportes SLA**: GET /reportes/disponibilidad?rango=24h|7d|30d (disponibilidad =
    (up+degraded)/evaluables). Pantalla "Reportes" (tabla + KPIs + CSV) y pantalla "Mapa" (contorno
    SVG de Colombia embebido, offline sin tiles, marcadores por sede según peor estado).
  - **Bitácora de auditoría** [migr. 0006]: tabla `auditoria`; AuditObserver de Eloquent en el CRUD
    de 8 entidades (con diff antes/después) + login; GET /auditoria (solo admin); pantalla "Auditoría".
  - **Interfaces Fase 2** [migr. 0007]: `interfaces_historico` (serie temporal Mbps, solo oper-up,
    purga 7 días), `interfaces.monitorear`, incidencias por interfaz (`if_index`/`if_nombre`, índice
    único ampliado a (recurso, COALESCE(if_index,-1))). Worker abre/cierra incidencia "puerto X caído"
    + notifica para interfaces monitoreadas (respeta mantenimiento y supresión por dependencia).
    API: PUT /recursos/{id}/interfaces/{ifIndex} (monitorear) y GET .../historico. UI: checkbox
    "Monitorear" + gráficas entrada/salida por puerto.
  - PENDIENTE del roadmap: canal Telegram (construido en Fase 5, falta configurar/probar) y Teams.

Nota de numeración: el usuario llamó "FASE 3" a los workers (en el plan original eran FASE 4).
Orden real ejecutado: estructura → datos → API → workers → frontend → notificaciones → despliegue → mejoras.

## Entorno de desarrollo (esta máquina)
- Windows + PowerShell. **NO** hay instalados: `docker`, `psql`, `php`, `composer`, `laravel`.
  → No se pueden ejecutar migraciones, `docker compose`, `php artisan` ni tests aquí;
  el código se escribe a mano y se verifica en la máquina del usuario. No reintentar
  estos comandos en local salvo que el usuario confirme que ya los instaló.