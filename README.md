# Sistema de Monitoreo de Disponibilidad de TI

Aplicación web para monitorear en tiempo casi-real la **disponibilidad** y la
**salud** de los recursos de TI de la entidad: firewalls, servidores, switches
LAN/SAN, NAS, UPS, enlaces Starlink, fibra WAN y sitios web. Detecta caídas,
degradaciones y recuperaciones, registra histórico y notifica.

## Arquitectura (monorepo, capas separadas)

```
monitoreo/
├── frontend/   # SPA Angular — consume REST + Supabase Realtime (no toca la BD)
├── api/        # REST en PHP/Laravel — CRUD, auth (valida JWT Supabase), reportes
├── monitor/    # Workers Python (APScheduler) — ejecutan probes y escriben en BD
├── db/         # Esquema PostgreSQL: migraciones + seed (portable a Postgres puro)
├── infra/      # docker-compose (Postgres local de desarrollo) + .env
└── docs/       # Documentación, incl. modelo-datos.md (diagrama del modelo)
```

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Frontend | Angular (LTS) | UI/SPA. REST + Realtime. No accede a la BD. |
| API | PHP + Laravel | CRUD, autenticación/JWT, configuración, umbrales, reportes. |
| Workers | Python + APScheduler | Probes por intervalo → `chequeos`, `metricas`, `incidencias`. |
| BD | PostgreSQL (Supabase → VM) | Estado, histórico y series temporales. |

> **Portabilidad:** la BD se diseña para Postgres estándar. Solo `pgcrypto`
> (contrib). Auth y Realtime de Supabase se aíslan en sus capas.

## Estado actual

- ✅ **FASE 0** — Estructura del monorepo + Postgres local en Docker.
- ✅ **FASE 1** — Modelo de datos (migraciones reversibles + seed + diagrama).
- ⏳ FASE 2 (API), FASE 3 (Frontend), FASE 4 (Workers) — pendientes.

## Arranque rápido (desarrollo)

### 1. Levantar la base de datos local
Requiere Docker.
```bash
cd infra
cp .env.example .env          # ajusta APP_CRYPTO_KEY (openssl rand -base64 48)
docker compose up -d          # primer arranque aplica migraciones + seed
```
- Postgres: `localhost:5432` (usuario/clave/db según `.env`).
- Adminer (explorador web): http://localhost:8080
- Reset total: `docker compose down -v && docker compose up -d`

Verificar:
```bash
docker compose exec db psql -U monitoreo -d monitoreo -c "\dt"
docker compose exec db psql -U monitoreo -d monitoreo -c "SELECT codigo, count(*) FROM recursos JOIN tipos_recurso t ON t.id = tipo_id GROUP BY codigo;"
```

### 2. (Próximas fases)
- **API:** `cd api && composer create-project laravel/laravel .`
- **Frontend:** `cd frontend && ng new monitoreo-frontend`
- **Workers:** `cd monitor && python -m venv .venv && pip install -r requirements.txt`

## Base de datos

Ver [db/README.md](db/README.md) para migraciones, mecanismo de cifrado de
secretos, agregación (rollup) y política de retención. El modelo lógico
completo (diagrama ER + flujo de datos) está en
[docs/modelo-datos.md](docs/modelo-datos.md).

## Convenciones

- Migraciones: `db/migrations/NNNN_nombre.up.sql` / `.down.sql` (reversibles).
- Secretos siempre cifrados (`recursos.secretos`, `canales_notificacion.secretos`);
  parámetros no sensibles en `parametros`/`config` (jsonb en claro).
- Nunca se versiona ningún `.env` (solo los `.env.example`).
