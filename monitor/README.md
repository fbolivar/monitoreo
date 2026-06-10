# monitor/ — Workers de monitoreo (Python)

Procesos headless que ejecutan los chequeos de disponibilidad según el intervalo
configurado por recurso, evalúan el estado contra los umbrales y escriben en
`chequeos`, `metricas` e `incidencias`. No exponen API pública (solo `/health`).

> **FASE 3:** probes **ICMP**, **HTTP/HTTPS** y **TCP**.
> **FASE 3b paso 1 (hecho):** **SNMP** v2c/v3 (servidores, switches LAN/SAN, NAS, UPS).
> **FASE 3b paso 2 (hecho):** **Starlink gRPC** (con fallback ICMP del gateway).
> **FASE 3b paso 3 (hecho):** **FortiGate API REST** (firewalls, clúster HA + failover).

## FortiGate API (FASE 3b · paso 3)

Probe [fortigate.py](monitor/monitor/probes/fortigate.py) (+ cliente aislado
[fortigate_client.py](monitor/monitor/probes/fortigate_client.py)). Selección
automática para el tipo `firewall`. **El clúster HA se modela como UN solo recurso.**

- Auth por token: `secretos.api_key` → `Authorization: Bearer`. SSL autofirmado:
  `parametros.verify_ssl` (por defecto `false`).
- Consulta `system/resource/usage` (cpu/mem/sesiones) y `system/ha-statistics`
  (miembros del clúster). `parametros.ha_miembros_esperados` (por defecto 2).
- **Estado del clúster:**
  - `up` (operativo): responde y, con HA, hay primario y nº de miembros == esperados.
  - `degraded`: falta un miembro **o** se detecta **failover** (el primario cambió
    respecto al último chequeo — comparación genérica en el runner vía `ha_primary`).
  - `down` (caído): sin respuesta de la API o clúster sin primario.
- Equipo standalone (sin HA): `up` si la API responde.

Métricas: `cpu` (%), `mem` (%), `sessions`, `ha_miembros`; en el detalle:
`ha_primary`, miembros, y `ha_failover`/`ha_primary_anterior` cuando aplica.

### Umbrales por defecto sugeridos

Aplicar (opcional) con [db/seeds/0004_umbrales_fortigate.sql](../db/seeds/0004_umbrales_fortigate.sql):

| Métrica | Op | Warning | Crítico |
|---|---|---|---|
| `cpu` | `>` | 75 | 90 |
| `mem` | `>` | 80 | 90 |
| `sessions` | `>` | (según modelo) | (según modelo) |

> El estado HA y el failover los decide el probe (no umbrales). `cpu`/`mem`/`sessions`
> pueden además escalar un clúster `up`/`degraded` a severidad crítica.

> **No validado contra un FortiGate real:** la E/S HTTP (httpx) solo se comprobó con
> `compileall`; el parseo de uso/HA, la detección de failover y la selección se
> ejecutaron en runtime. Los nombres de campos de `ha-statistics` varían según FortiOS;
> ajustar `_CLAVES_PRIMARIO`/`parsear_ha` si hace falta.

## Starlink gRPC (FASE 3b · paso 2)

Probe [starlink.py](monitor/monitor/probes/starlink.py) (+ cliente aislado
[starlink_client.py](monitor/monitor/probes/starlink_client.py)). Selección
automática para el tipo `starlink`.

- Consulta `get_status` al dish en `192.168.100.1:9200` por gRPC con reflexión
  (`yagrc`, sin compilar protos). `parametros.grpc_host`/`grpc_port` lo sobreescriben.
- **Fallback:** si no hay acceso gRPC al dish (timeout/error), hace **ICMP al
  gateway** (`parametros.gateway` o el `hostname`); el `detalle` marca
  `fuente: icmp-fallback`.
- `estado_base = down` si `pop_ping_drop_rate >= 1.0` (sin servicio); si no, `up`
  y los umbrales determinan degradación.

Métricas: `latency` (ms), `loss` (%), `obstruccion` (%), `throughput_down` (Mbps),
`throughput_up` (Mbps); `uptime_s` en el detalle.

### Umbrales por defecto sugeridos

Aplicar (opcional) con [db/seeds/0003_umbrales_starlink.sql](../db/seeds/0003_umbrales_starlink.sql):

| Métrica | Op | Warning | Crítico |
|---|---|---|---|
| `latency` | `>` | 150 | 400 |
| `loss` | `>` | 2 | 10 |
| `obstruccion` | `>` | 1 | 5 |
| `throughput_down` | `<` | 20 | 5 (ajustar al plan) |

> **No validado contra un dish real:** la E/S gRPC (grpcio/yagrc) solo se comprobó
> con `compileall`; el parseo del status y la selección/fallback sí en runtime.
> El nombre exacto de algunos campos del status puede variar según el firmware
> del dish: ajustar en `parsear_status` si hace falta.

## SNMP (FASE 3b · paso 1)

Probe [snmp.py](monitor/monitor/probes/snmp.py) (+ cliente aislado
[snmp_client.py](monitor/monitor/probes/snmp_client.py)). Selección automática
para los tipos `servidor`, `switch_lan`, `switch_san`, `nas`, `ups`, o cualquier
recurso con `parametros.metodo = "snmp"`.

Credenciales (descifradas vía pgcrypto, igual que la API):
- **v2c:** `secretos.snmp_community`.
- **v3:** `secretos.snmp_user`, `secretos.snmp_auth`, `secretos.snmp_priv`;
  protocolos en `parametros.auth_protocol` (MD5|SHA) y `parametros.priv_protocol`
  (DES|AES). El nivel (noAuth/authNoPriv/authPriv) se deduce de las claves presentes.

**Equipos genéricos** (switch/servidor/NAS/SAN): consulta los OIDs de
`parametros.oids` = `{ "cpu": "1.3.6...", "mem": "1.3.6...", ... }` y guarda cada
uno como métrica con ese nombre. Reachability por `sysUpTime`.

**UPS** (UPS-MIB / RFC 1628), métricas fijas:

| Métrica | OID | Unidad |
|---|---|---|
| `bateria` | upsEstimatedChargeRemaining `…33.1.2.4.0` | % |
| `autonomia_min` | upsEstimatedMinutesRemaining `…33.1.2.3.0` | min |
| `carga` | upsOutputLoad `…33.1.4.4.1.5.1` | % |
| `estado_linea` | upsOutputSource `…33.1.4.1.0` | enum (3=normal, 5=batería…) |
| `battery_status` | upsBatteryStatus `…33.1.2.1.0` | enum (2=normal,3=baja,4=agotada) |

### Umbrales por defecto sugeridos

Aplicar (opcional) con [db/seeds/0002_umbrales_snmp.sql](../db/seeds/0002_umbrales_snmp.sql):

| Tipo | Métrica | Op | Warning | Crítico |
|---|---|---|---|---|
| servidor/switch_lan/switch_san/nas | `cpu` | `>` | 80 | 95 |
| servidor/switch_lan/switch_san/nas | `mem` | `>` | 85 | 95 |
| nas | `vol_used` | `>` | 80 | 90 |
| ups | `bateria` | `<` | 50 | 20 |
| ups | `autonomia_min` | `<` | 10 | 5 |
| ups | `carga` | `>` | 80 | 90 |
| ups | `estado_linea` | `!=` | — | 3 (≠normal ⇒ crítico) |
| ups | `battery_status` | `>=` | 3 | 4 |

> **No validado contra equipos reales:** la E/S SNMP (pysnmp) solo se comprobó con
> `compileall`; las funciones de parseo/mapeo/credenciales/selección sí se ejecutaron
> en runtime. Verificar contra un dispositivo real antes de dar por buena esta capa.

## Estructura

```
monitor/
├── main.py                 # entrypoint: arranca pool + scheduler + health
├── requirements.txt
├── .env.example
└── monitor/
    ├── config.py           # settings desde .env (DB, cifrado, probes, scheduler)
    ├── db.py               # pool de conexiones psycopg 3
    ├── models.py           # Recurso, Umbral
    ├── repository.py       # TODAS las queries SQL
    ├── evaluacion.py       # lógica PURA: estado vs umbrales (testeable)
    ├── runner.py           # un ciclo de chequeo + máquina de incidencias
    ├── scheduler.py        # APScheduler: job por recurso + tareas internas
    ├── health.py           # /health opcional (stdlib)
    └── probes/
        ├── __init__.py     # selección de probe por recurso
        ├── base.py         # Muestra, ResultadoProbe, Probe
        ├── icmp.py         # ping (RTT + pérdida)
        ├── http.py         # status + latencia + días SSL
        └── tcp.py          # conexión a puerto
```

## Puesta en marcha

Requiere Python 3.11+ y la BD de `/db` migrada (Postgres local de `/infra` o Supabase).

```bash
cd monitor
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env           # ajustar DB_*, APP_CRYPTO_KEY (igual que API/infra)
python main.py
```

> **ICMP y privilegios:** en Windows el ping ICMP suele requerir privilegios
> (`ICMP_PRIVILEGED=true`, ejecutar como administrador). En Linux/macOS puede ir
> en `false` (sockets datagram).

## Cómo decide el estado

Ver el flujo completo en [../docs/flujo-chequeo.md](../docs/flujo-chequeo.md).
Resumen:

| Situación | estado | severidad |
|---|---|---|
| Responde, métricas OK | `up` | — |
| Responde, métrica sobre umbral warning | `degraded` | `warning` |
| Responde, métrica sobre umbral crítico | `degraded` | `critical` |
| No responde / status incorrecto | `down` | `critical` |
| No evaluable (sin host / protocolo 3b) | `unknown` | `warning` |
| En ventana de mantenimiento | `maintenance` | (sin incidencia) |

- **Incidencias:** `down` abre de inmediato; `degraded` respeta `duracion_segundos`
  (anti-flapping); volver a `up` **resuelve** la incidencia abierta.
- **Mantenimiento:** durante la ventana se registran chequeos/métricas pero **no**
  se abren/cierran incidencias.

## Notificaciones (FASE 5)

Cuando se **abre** o **cierra** una incidencia (y en **escalamientos** de severidad),
el worker notifica por los canales activos. Implementado en
[notificaciones/](monitor/notificaciones/) (motor + emisores) y cableado en el
[runner](monitor/monitor/runner.py); reintentos como job del scheduler.

- **Canales:** `email` (SMTP), `telegram` (Bot API), `webhook` (POST JSON).
  Config no sensible en `canales_notificacion.config`; secretos (tokens, smtp_pass)
  cifrados y descifrados vía pgcrypto, **igual que la API**.
- **Deduplicación:**
  - por `(incidencia, canal, evento)`: nunca se reenvía el mismo evento;
  - **anti-flapping**: una `apertura` del mismo recurso no se reenvía dentro de
    `NOTIF_DEDUP_COOLDOWN_SEG` (evita spamear la misma caída si oscila).
- **Escalamiento por severidad:** cada canal puede fijar `config.min_severidad`
  (`info|warning|critical`); solo recibe eventos de severidad ≥ ese mínimo
  (critical escala a más canales). Si una incidencia abierta sube de severidad
  (p. ej. `warning → critical`) se emite un evento de **escalamiento**.
- **Mantenimiento:** durante una ventana no se abren/cierran incidencias, por lo
  que **no se notifica** (silencio total heredado del runner).
- **Registro y reintentos:** cada envío se guarda en `notificaciones`
  (`enviada`/`fallida`, `intentos`, `error`, `enviada_at`). Un job reintenta las
  fallidas hasta `NOTIF_MAX_INTENTOS` cada `NOTIF_RETRY_INTERVAL_SEG`.

Ejemplo de `config` por canal:
```jsonc
// email
{ "smtp_host": "smtp.entidad.gov.co", "smtp_port": 587,
  "from": "noc@entidad.gov.co", "destinatarios": ["noc@entidad.gov.co"],
  "min_severidad": "warning" }     // secretos: { "smtp_user": "...", "smtp_pass": "..." }
// telegram
{ "chat_id": "-1001234567890", "min_severidad": "critical" }  // secretos: { "bot_token": "..." }
// webhook
{ "url": "https://hooks.entidad.local/alertas" }              // secretos: { "token": "..." }
```

## Secretos

Los probes que los necesitan (HTTP con basic-auth o api_key) los obtienen
descifrando con `descifrar_secreto(secretos, APP_CRYPTO_KEY)` — la **misma**
función pgcrypto que usa la API. La clave maestra vive solo en el `.env` del worker.

## Tests

```bash
pip install pytest
pytest
```

- [tests/test_evaluacion.py](tests/test_evaluacion.py): mapeo estado/severidad,
  operadores, peor severidad entre métricas (lógica pura, sin BD ni red).
- [tests/test_seleccion_probe.py](tests/test_seleccion_probe.py): selección de probe.

> Estos tests no requieren BD ni dependencias de red. Validados además con
> `python -m compileall` (sintaxis de todo el paquete).
