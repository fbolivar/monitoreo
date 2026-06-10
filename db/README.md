# db/ — Esquema, migraciones y seed (PostgreSQL)

Todo el SQL es **Postgres 14+ estándar**. La única dependencia es la extensión
contrib `pgcrypto` (presente en Supabase y en Postgres puro). **No** se usan
funciones ni tipos propietarios de Supabase → el esquema es portable a un
Postgres en servidor virtual sin cambios.

## Estructura

```
db/
├── migrations/
│   ├── 0001_init.up.sql        # extensiones, cifrado, tablas núcleo
│   ├── 0001_init.down.sql      # reversa de 0001
│   ├── 0002_timeseries.up.sql  # métricas particionadas + rollup + purga
│   └── 0002_timeseries.down.sql
└── seeds/
    └── 0001_seed.sql           # 2-3 recursos por tipo + telemetría de ejemplo
```

Convención: `NNNN_nombre.up.sql` aplica, `NNNN_nombre.down.sql` revierte.
Se aplican en orden numérico ascendente; se revierten en orden descendente.

## Cómo aplicar

### Opción A — Postgres local con Docker (recomendado en dev)
Desde `/infra`, el primer arranque aplica migraciones + seed automáticamente:
```bash
cd infra
cp .env.example .env          # ajusta APP_CRYPTO_KEY
docker compose up -d
```

### Opción B — psql manual (contra cualquier Postgres / Supabase)
```bash
export APP_CRYPTO_KEY="<tu-clave>"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/0001_init.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v app_crypto_key="$APP_CRYPTO_KEY" -f db/migrations/0002_timeseries.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v app_crypto_key="$APP_CRYPTO_KEY" -f db/seeds/0001_seed.sql
```
> `0001_init` no necesita la clave; `0002` tampoco la usa, pero pasarla no estorba.
> El **seed** sí la requiere (cifra los secretos de ejemplo).

### Revertir
```bash
psql "$DATABASE_URL" -f db/migrations/0002_timeseries.down.sql
psql "$DATABASE_URL" -f db/migrations/0001_init.down.sql
```

## Cifrado de secretos (mecanismo propuesto)

- **Datos en claro** → `recursos.parametros` (jsonb): puerto, versión SNMP, OIDs,
  path HTTP, timeouts, etc. Lo NO sensible.
- **Secretos** → `recursos.secretos` (bytea): community SNMP, api_key, password,
  tokens. Se almacenan **cifrados** con `pgp_sym_encrypt` (AES-256) vía los
  helpers `cifrar_secreto(jsonb, clave)` / `descifrar_secreto(bytea, clave)`.
- La **clave maestra** (`APP_CRYPTO_KEY`) **NO se guarda en la base de datos**.
  La posee la API (Laravel `.env`) y se pasa como argumento en cada operación.
  Los workers reciben la clave por su propio entorno o piden el secreto a la API.

Ejemplo de descifrado (solo la app debe hacerlo, con su clave):
```sql
SELECT id, nombre, descifrar_secreto(secretos, 'LA_CLAVE') AS secreto
FROM recursos WHERE secretos IS NOT NULL;
```

> Alternativa equivalente y también portable: cifrar/descifrar en la aplicación
> (libsodium/AES-GCM) y guardar el ciphertext en `bytea`. Se eligió pgcrypto por
> mantener la lógica junto al dato y evitar exponer claves al transportar jsonb.

## Series temporales y retención escalonada

`metricas` está **particionada por mes** (`PARTITION BY RANGE (ts)`), con índice
`(recurso_id, metrica, ts)` para consultas por rango de fechas.

Agregación (rollup) y purga (todo en SQL portable, sin pg_cron obligatorio —
los invoca el worker Python con APScheduler, o `pg_cron` donde exista):

| Función | Qué hace |
|---|---|
| `fn_crear_particion_metricas(fecha)` | Crea la partición mensual (idempotente). |
| `fn_drop_particiones_metricas(antes)` | Elimina particiones mensuales antiguas. |
| `fn_rollup_metricas_horario(desde, hasta)` | `metricas` → agregado horario. |
| `fn_rollup_metricas_diario(desde, hasta)`  | horario → agregado diario. |
| `fn_purgar_datos(...)` | Aplica la retención escalonada. |

**Política de retención (propuesta):**

| Dato | Tabla | Retención |
|---|---|---|
| Chequeos crudos | `chequeos` | 30 días |
| Métricas crudas | `metricas` | 15 días |
| Agregado horario | `metricas_rollup_horario` | 90 días |
| Agregado diario | `metricas_rollup_diario` | 730 días (2 años) |
| Incidencias | `incidencias` | indefinido (histórico) |

## Catálogo de estados (propuesto)

`up` · `degraded` · `down` · `unknown` · `maintenance`
(incidencia: `abierta`/`reconocida`/`resuelta`; severidad: `info`/`warning`/`critical`).

> Tanto el catálogo de estados como la política de retención **no estaban
> definidos en `CLAUDE.md`** (la sección quedó vacía); aquí van como propuesta
> para tu visto bueno.
