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
  - Canales: Telegram (motor Fase 5; falta configurar bot_token/chat_id) y Teams (sender provisto,
    Incoming Webhook MessageCard; tipo 'teams' permitido) — implementados, sin configurar aún.

- ✅ MEJORAS 2ª OLA (mercado, 2026-06-11) — todas en producción y verificadas (commit 6b831a2):
  - **Escalado por tiempo (on-call)** [migr. 0008]: `incidencias.escalada_at`; job APScheduler
    `escalar_incidencias` (cada `ESCALATION_CHECK_SEG`); si una incidencia 'abierta' supera
    `ESCALATION_MIN` (def 15) sin reconocerse, reenvía evento `escalada_tiempo`. Reconocer la detiene.
  - **Tablero NOC (wallboard)**: ruta `/wallboard` a pantalla completa (fuera del Shell), tema oscuro,
    autorefresco, KPIs + tiles por sede coloreados (parpadeo en caídas). Para sala de operaciones.
  - **Grafana**: instalado en `:3000` (script `19_grafana.sh`); rol Postgres RO `grafana_ro`
    (clave en `GRAFANA_RO_PW`); datasource + dashboard autoprovisionados (`infra/grafana/`). ufw 3000.
  - **Receptor de SNMP traps** [migr. 0009]: servicio systemd `simon-traps` (`monitor/trap_listener.py`,
    pysnmp ntfrcv UDP/162, community `TRAP_COMMUNITY`); mapea IP→recurso; clasifica
    linkDown/linkUp/cold-warmStart/authFailure; tabla `traps`; GET `/api/traps`; pantalla "Traps".
    Pasa de sondeo a TIEMPO REAL en eventos de red. ufw 162/udp.
  - **SSO AD/LDAP** (env-gated) [migr. 0010, `origen`]: `config/ldap.php` + `App\Support\Ldap` (bind
    simple); `AuthController` intenta local y luego LDAP si `AUTH_LDAP_ENABLED`; crea perfil
    `origen='ldap'` al primer ingreso. Requiere `php8.2-ldap` (instalado). Sin configurar (sin AD).
  - **2FA TOTP** [migr. 0010, `totp_secret`/`totp_activo`]: `App\Support\Totp` (RFC 6238, sin deps);
    `DosFactorController` (`/api/2fa/iniciar|activar|desactivar`); login pide `codigo` y responde
    `{requiere_2fa:true}` si falta; pantalla "Seguridad". Solo cuentas locales (LDAP usa el 2FA del AD).
  Guía operativa de todo en `docs/funcionalidades-avanzadas.md`.

- ✅ MEJORAS 3ª OLA (mercado, 2026-06-11) — en producción y verificadas (commits 337797e, 324a65f):
  - **Traps → incidencias (tiempo real)**: el receptor `simon-traps` ya no solo registra; un trap
    **linkDown** abre una incidencia de interfaz (reusa el modelo de incidencias por `if_index`) y
    notifica; **linkUp** la cierra. Más rápido que el sondeo.
  - **Dead-man's switch**: `runner.latido_externo` + job; envs `DEADMAN_URL` (vacío=off),
    `DEADMAN_INTERVAL_SEG`. Hace `db.ping()` y un GET a la URL; si el worker/BD cae, el servicio
    externo (healthchecks.io/UptimeRobot…) alerta. "¿Quién vigila al vigilante?".
  - **Pollers distribuidos (base)**: env `WORKER_SITIOS="3,7"` → el worker solo atiende esos sitios.
    Permite un worker por sede/parque remoto (tras NAT/Starlink) que escribe en la BD central.
    Guía: `docs/pollers-distribuidos.md`. Fleet mgmt completo = follow-up.
  - **Respaldo de configuración** [migr. 0012 `config_respaldos`]: job diario (02:00)
    `respaldar_configuraciones`; baja la config del FortiGate (POST `/api/v2/monitor/system/config/backup`
    — OJO POST, GET da 405 en FortiOS 7.6). Guarda **solo si cambió** (hash sha256) con **diff**
    unificado y **avisa** del cambio (`motor.notificar_simple`, sin incidencia). API
    `GET /recursos/{id}/respaldos[/{rid}]`; UI: sección "Respaldos de configuración" en el detalle.
    Backup de switches por SSH = follow-up.

- ✅ MEJORAS 4ª OLA — Endurecimiento de seguridad/cumplimiento (2026-06-11, commit 5b0e254), verificado:
  - **Bloqueo por fuerza bruta**: tras `AUTH_MAX_INTENTOS` (def 5) login_fallido del mismo usuario en
    `AUTH_LOCKOUT_MIN` (def 15) min, el login responde **429** (temporal, por usuario). Reusa la tabla
    `auditoria` (no hay tabla nueva). AuthController::intentosFallidos.
  - **Política de contraseñas** (cuentas locales): `Password::min(12)->mixedCase()->numbers()->symbols()`
    en PerfilController store/update. Los usuarios LDAP usan la política del AD.
  - **Cierre por inactividad** (frontend): `IdleService` cierra sesión tras `environment.idleMinutes`
    (def 30) sin actividad; activo en el `Shell` (NO en el wallboard). Login muestra aviso
    (?motivo=inactividad).
  - **Cert de CA interna** (quita el warning HTTPS): guiado. `infra/deploy/cert_csr.sh` genera clave+CSR
    para firmar con la CA de AD (los PCs del dominio ya la confían por GPO); luego instalar .crt +
    ajustar nginx (ssl_certificate, server_name bc360.pnnc.local). NO ejecutado (requiere la CA del usuario).

- ✅ MEJORAS 5ª OLA — Profundidad técnica del monitoreo (Tier 1) (2026-06-15), worker verificado (67 tests) + `ng build` OK:
  - **Estados SOFT/HARD (anti-falsos-positivos)** [migr. 0013]: un estado "malo" (down/degraded/unknown)
    solo se confirma como HARD tras N chequeos consecutivos (`MAX_CHECK_ATTEMPTS`, def 3; override por
    recurso en `recursos.max_check_attempts`); solo las transiciones HARD abren/cierran incidencias y
    notifican. Recuperación a 'up' configurable (`RECOVERY_ATTEMPTS`, def 1 = inmediata). `recursos.estado_actual`
    pasa a reflejar el HARD (dashboard estable); `chequeos` guarda el estado CRUDO + `detalle.soft`
    (candidato/intentos). Máquina pura `evaluacion.confirmar_estado`. Mata los falsos positivos por un
    timeout/paquete perdido puntual (clave con Starlink).
  - **Triggers compuestos (multi-condición)** [migr. 0014, tabla `reglas`]: expresión booleana AST en jsonb
    sobre varias métricas (`and`/`or`/`not` + hojas `{metrica,op,valor}`), evaluada por un intérprete puro
    seguro (`monitor/reglas.py`, sin `eval`); al cumplirse, degrada con la severidad indicada (peor de
    umbrales+reglas). Lógica trivaluada: una métrica ausente no dispara (sin falsas alarmas). API
    `ReglaController` (CRUD + validación del AST, espejo en PHP), rutas en `$crud`, auditada. UI: pestaña
    "Reglas" en Configuración (editor de expresión JSON con ejemplo).
  - **Freshness / stale-data** [sin migración]: job `marcar_obsoletos` (`FRESHNESS_CHECK_SEG`); si un recurso
    activo lleva más de `FRESHNESS_FACTOR`×intervalo (piso `FRESHNESS_MIN_SEG`) sin chequeo, se marca
    'unknown' (cubre un job muerto o un recurso que dejó de responder en silencio). Respeta mantenimiento y
    pollers distribuidos. No abre incidencia (política de 'unknown').
  Nota: el motor (Python) se validó con tests puros; la E/S contra equipos reales y la API/UI las verifica
  el usuario en el servidor (sin php/ng aquí salvo `ng build`).

- ✅ MEJORAS 6ª OLA — Profundidad técnica (Tier 2) (2026-06-15), worker verificado (77 tests) + `ng build` OK,
  DESPLEGADO en producción:
  - **ICMP enriquecido** [sin migración]: el probe ICMP emite además `jitter`, `rtt_min`, `rtt_max`
    (antes solo latency+loss). Distingue "enlace degradado" (pérdida/jitter alto) de "caído" en WAN/Starlink
    vía umbrales/reglas. Helper puro `construir_muestras_icmp` (testeable).
  - **Forecasting de capacidad** [migr. 0015, tabla `pronosticos`]: job diario `pronosticar_capacidad`
    (00:30, tras el rollup) que ajusta una **regresión lineal pura** (`monitor/forecast.py`, sin numpy)
    sobre el rollup diario de métricas % (disco_*/mem) y proyecta los **días hasta el 100%**. Avisa
    (sin incidencia, `notificar_simple`) al cruzar por debajo de `FORECAST_ALERT_DIAS` (def 14); solo si
    el ajuste tiene confianza `r2 >= FORECAST_MIN_R2` (def 0.5) y ≥ `FORECAST_MIN_DIAS` (def 5) de historia.
    API `GET /pronosticos` (lectura; los calcula el worker). UI: panel "Pronóstico de capacidad" en Reportes.
  - **Ajuste de scheduler** (de la 5ª ola, consolidado en repo): `SCHEDULER_MAX_WORKERS=50`, `MISFIRE_GRACE=90`
    (evita que sondas SNMP lentas descarten jobs web por misfire).
  - DEFERIDO: baselining estacional / detección de anomalías (Tier 2 #5) — requiere calibración con datos
    maduros para no meter ruido en el lazo de alertas; se hará en iteración propia.

Nota de numeración: el usuario llamó "FASE 3" a los workers (en el plan original eran FASE 4).
Orden real ejecutado: estructura → datos → API → workers → frontend → notificaciones → despliegue → mejoras.

## Entorno de desarrollo (esta máquina)
- Windows + PowerShell. **NO** hay instalados: `docker`, `psql`, `php`, `composer`, `laravel`.
  → No se pueden ejecutar migraciones, `docker compose`, `php artisan` ni tests aquí;
  el código se escribe a mano y se verifica en la máquina del usuario. No reintentar
  estos comandos en local salvo que el usuario confirme que ya los instaló.