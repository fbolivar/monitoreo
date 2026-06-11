# SIMON — Sistema Integral de Monitoreo

Aplicación web (identidad **Parques Nacionales Naturales de Colombia**) para
monitorear en tiempo casi-real la **disponibilidad** y la **salud** de los recursos
de TI de la entidad: firewalls, servidores, switches LAN/SAN, NAS, UPS, enlaces
Starlink, fibra WAN y sitios web. Detecta caídas, degradaciones y recuperaciones,
registra histórico y notifica.

> **Autenticación LOCAL** (JWT propio HS256, sin Supabase) y dashboard "en vivo"
> por **polling** al API. La BD es un PostgreSQL estándar en servidor.

## Arquitectura (monorepo, capas separadas)

```
monitoreo/
├── frontend/   # SPA Angular 20 — consume la API REST por polling (no toca la BD)
├── api/        # REST en PHP/Laravel — CRUD, auth (JWT local), reportes, auditoría
├── monitor/    # Workers Python (APScheduler) — ejecutan probes y escriben en BD
├── db/         # Esquema PostgreSQL: migraciones + seed (portable a Postgres puro)
├── infra/      # docker-compose (Postgres local de desarrollo) + deploy/ (scripts servidor)
└── docs/       # Documentación (modelo-datos.md, flujo-chequeo.md, funcionalidades-avanzadas.md)
```

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Frontend | Angular 20 (standalone + signals) | UI/SPA. REST + polling. No accede a la BD. |
| API | PHP 8.2 + Laravel 11 | CRUD, auth (JWT local), configuración, umbrales, reportes, auditoría. |
| Workers | Python + APScheduler | Probes por intervalo → `chequeos`, `metricas`, `incidencias`, `interfaces`. |
| BD | PostgreSQL | Estado, histórico y series temporales. |

> **Portabilidad:** la BD usa Postgres estándar; solo `pgcrypto` (contrib). Sin Supabase.

## Estado actual — EN PRODUCCIÓN (192.168.50.54)

Todas las fases completas (estructura → datos → API → workers → frontend →
notificaciones → despliegue) y las **mejoras de operación** del roadmap:

- ✅ Interfaces SNMP (IF-MIB) con throughput por puerto · histórico + gráficas · alerta por puerto.
- ✅ Dependencias padre→hijo (anti-tormenta de alertas).
- ✅ Reportes de disponibilidad/SLA (CSV) y mapa de sedes (SVG offline).
- ✅ Bitácora de auditoría (CRUD + login, solo admin).
- ⏳ Pendiente: canal Telegram (configurar/probar) y Microsoft Teams.

Detalle operativo de cada una en [`docs/funcionalidades-avanzadas.md`](docs/funcionalidades-avanzadas.md).
El detalle por fases vive en [`CLAUDE.md`](CLAUDE.md).

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
