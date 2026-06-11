# Modelo lógico de datos — Sistema de Monitoreo de Disponibilidad de TI

> Generado en FASE 1. Refleja `db/migrations/0001_init.up.sql` y
> `db/migrations/0002_timeseries.up.sql`.

## Diagrama entidad-relación (mermaid)

```mermaid
erDiagram
    tipos_recurso ||--o{ recursos : "clasifica"
    tipos_recurso ||--o{ umbrales : "aplica por tipo"
    sitios        ||--o{ recursos : "ubica"
    sitios        ||--o{ mantenimientos : "alcanza"
    recursos      ||--o{ chequeos : "registra"
    recursos      ||--o{ metricas : "emite"
    recursos      ||--o{ umbrales : "aplica por recurso"
    recursos      ||--o{ incidencias : "genera"
    recursos      ||--o{ mantenimientos : "programa"
    recursos      ||--o{ metricas_rollup_horario : "agrega"
    recursos      ||--o{ metricas_rollup_diario : "agrega"
    chequeos      ||--o| incidencias : "abre (chequeo_apertura_id)"
    incidencias   ||--o{ notificaciones : "dispara"
    canales_notificacion ||--o{ notificaciones : "entrega"
    perfiles      ||--o{ incidencias : "reconoce"
    perfiles      ||--o{ mantenimientos : "crea"

    tipos_recurso {
        smallint id PK
        text     codigo UK
        text     nombre
        text     protocolo_default
    }
    sitios {
        int     id PK
        text    codigo UK
        text    nombre
        numeric latitud
        numeric longitud
        bool    activo
    }
    perfiles {
        uuid id PK "= auth.users.id (sin FK)"
        text email UK
        text rol "admin|operador|viewer"
        bool activo
    }
    recursos {
        bigint   id PK
        smallint tipo_id FK
        int      sitio_id FK
        text     nombre
        text     hostname
        jsonb    parametros "NO sensible"
        bytea    secretos "cifrado pgcrypto"
        int      intervalo_segundos
        bool     activo
        text     estado_actual "up|degraded|down|unknown|maintenance"
        timestamptz ultimo_chequeo_at
    }
    chequeos {
        bigint   id PK
        bigint   recurso_id FK
        timestamptz ts
        text     estado
        int      latencia_ms
        jsonb    detalle
    }
    metricas {
        bigint   recurso_id PK,FK
        text     metrica PK
        timestamptz ts PK
        float    valor
        text     unidad
    }
    metricas_rollup_horario {
        bigint   recurso_id PK,FK
        text     metrica PK
        timestamptz bucket PK
        float    valor_avg
        float    valor_min
        float    valor_max
        int      muestras
    }
    metricas_rollup_diario {
        bigint   recurso_id PK,FK
        text     metrica PK
        date     bucket PK
        float    valor_avg
        int      muestras
    }
    umbrales {
        bigint   id PK
        bigint   recurso_id FK "XOR tipo_id"
        smallint tipo_id FK
        text     metrica
        text     operador
        float    valor_warning
        float    valor_critical
        int      duracion_segundos
    }
    incidencias {
        bigint   id PK
        bigint   recurso_id FK
        text     estado "abierta|reconocida|resuelta"
        text     severidad "info|warning|critical"
        text     titulo
        bigint   chequeo_apertura_id FK
        uuid     reconocida_por FK
        timestamptz abierta_at
        timestamptz resuelta_at
    }
    mantenimientos {
        bigint   id PK
        bigint   recurso_id FK
        int      sitio_id FK
        timestamptz inicio
        timestamptz fin
        text     motivo
        uuid     creado_por FK
    }
    canales_notificacion {
        bigint   id PK
        text     tipo "email|sms|webhook|slack|telegram"
        text     nombre
        jsonb    config "NO sensible"
        bytea    secretos "cifrado pgcrypto"
        bool     activo
    }
    notificaciones {
        bigint   id PK
        bigint   incidencia_id FK
        bigint   canal_id FK
        text     estado "pendiente|enviada|fallida"
        text     destino
        int      intentos
        timestamptz enviada_at
    }
```

## Flujo de datos (cómo se llena el modelo)

```mermaid
flowchart LR
    W[Worker Python<br/>APScheduler] -->|probe según intervalo| R[(recursos)]
    W -->|resultado crudo| C[(chequeos)]
    W -->|telemetría| M[(metricas)]
    W -->|evalúa umbrales| U[(umbrales)]
    U -->|supera warning/critical| I[(incidencias)]
    I -->|reglas de salida| N[(notificaciones)]
    N --> CH[(canales_notificacion)]
    M -->|fn_rollup_horario| RH[(rollup_horario)]
    RH -->|fn_rollup_diario| RD[(rollup_diario)]
    M -. fn_purgar_datos 15d .-> X((purga))
    C -. 30d .-> X
    RH -. 90d .-> X
    RD -. 730d .-> X
    MNT[(mantenimientos)] -.silencia.-> I
```

## Notas de diseño

- **Capas separadas (CLAUDE.md):** la BD no contiene lógica de Supabase. `perfiles.id`
  es un `uuid` que coincide con `auth.users.id`, pero **sin FK** → portable a Postgres puro.
- **Cifrado:** `parametros` (jsonb, claro) vs `secretos` (bytea, cifrado pgcrypto AES-256).
  La clave maestra vive en la API, nunca en la BD. Ver `db/README.md`.
- **Serie temporal:** `metricas` particionada por mes (RANGE nativo, sin TimescaleDB),
  indexada por `(recurso_id, metrica, ts)` para consultas por rango.
- **Retención escalonada:** crudo 15d → horario 90d → diario 730d; chequeos 30d.
- **Estados:** `up | degraded | down | unknown | maintenance`.
- **Una incidencia abierta por (recurso, interfaz)** garantizada por índice único parcial
  `uq_incidencia_abierta` sobre `(recurso_id, COALESCE(if_index, -1)) WHERE estado <> 'resuelta'`.
  La incidencia "del recurso" usa `if_index NULL`; las de interfaz llevan su `if_index`.

## Tablas y columnas añadidas (mejoras de operación)

Migraciones 0004–0007 (ver `db/migrations/` y `docs/funcionalidades-avanzadas.md`):

- **0004 `interfaces`** — snapshot por puerto (IF-MIB): `oper_estado`, `admin_estado`,
  `in_mbps`/`out_mbps`, `util_*`, `*_err`, `speed_mbps`. PK `(recurso_id, if_index)`.
- **0005 `recursos.depende_de_id`** — self-FK para dependencias padre→hijo (supresión de alertas).
- **0006 `auditoria`** — bitácora: `perfil_id`, `actor_email/rol`, `accion`, `entidad`,
  `entidad_id`, `cambios` (jsonb diff), `ip`.
- **0007** — `interfaces_historico` (serie temporal de Mbps por puerto, retención 7d),
  `interfaces.monitorear` (alertar si cae), e `incidencias.if_index`/`if_nombre` (incidencias por interfaz).

> El catálogo de estados y la política de retención son **propuestas** de esta
> fase: la sección correspondiente de `CLAUDE.md` estaba vacía.
