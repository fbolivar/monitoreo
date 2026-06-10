# frontend/ — SPA Angular 20 (panel NOC)

SPA en **Angular 20** (standalone + signals). Consume la **API PHP** por REST y
**Supabase** para Auth + Realtime. **No** accede a la BD directamente.

> Generada con Angular CLI 20.3. Tema oscuro denso orientado a operación NOC.

## Estado (FASE 4 — completa, validada con `ng build`)

- ✅ Base: Supabase Auth (login/sesión), guard de rutas, interceptor JWT a la API,
  capa de servicios, layout NOC, autorización por rol.
- ✅ **P1 Dashboard** — semáforo por **sitio** y **tipo** + **Supabase Realtime**.
- ✅ **P2 Detalle de recurso** — gráficas SVG por métrica (1h/24h/7d), último chequeo,
  línea de tiempo de incidencias con duración.
- ✅ **P3 Gestión de recursos** — CRUD (parámetros + secretos write-only), gated por rol.
- ✅ **P4 Incidencias** — activas/histórico, severidad, duración.
- ✅ **P5 Configuración** — umbrales, mantenimientos y canales (CRUD, gated por rol).
- ⏳ Notificaciones — fase aparte (pendiente de OK).

## Puesta en marcha

Requiere Node ≥ 20.19 / 24. (Probado con Node 24, Angular 20.3.)

```bash
cd frontend
npm install
# Configurar src/environments/environment.ts:
#   apiUrl          -> base de la API Laravel (incluye /api), p.ej. http://localhost:8000/api
#   supabaseUrl     -> Supabase > Settings > API > Project URL
#   supabaseAnonKey -> Supabase > Settings > API > anon public key
npm start            # ng serve -> http://localhost:4200
npm run build        # build de producción (validado)
```

> **Realtime:** para que el Dashboard se actualice en vivo, activar Realtime en
> Supabase para las tablas `recursos` e `incidencias` (Database → Replication →
> publicación `supabase_realtime`).

## Arquitectura

```
src/
├── environments/environment.ts      # apiUrl + credenciales Supabase
├── styles.scss                      # tema NOC + variables de semáforo
└── app/
    ├── core/
    │   ├── supabase.client.ts        # cliente Supabase (Auth + Realtime)
    │   ├── auth.service.ts           # sesión + perfil/rol (signals); rol vía /api/me
    │   ├── guards.ts                 # authGuard / editorGuard / adminGuard
    │   ├── auth.interceptor.ts       # añade el JWT a las llamadas a la API
    │   ├── api.service.ts            # wrapper HTTP
    │   ├── recursos.service.ts       # /recursos, /tipos-recurso, /sitios
    │   ├── telemetria.service.ts     # /chequeos, /metricas, /incidencias
    │   ├── realtime.service.ts       # suscripciones Realtime
    │   └── models.ts                 # tipos (espejo de la API)
    ├── layout/shell.ts               # marco NOC (nav + topbar)
    ├── shared/estado-badge.ts        # semáforo reutilizable
    └── features/
        ├── auth/login.ts
        ├── dashboard/                # ✅ Pantalla 1 (Realtime)
        ├── recurso-detalle/          # ⏳ Pantalla 2
        ├── recursos/                 # ⏳ Pantalla 3
        ├── incidencias/              # ⏳ Pantalla 4
        └── configuracion/            # ⏳ Pantalla 5
```

## Roles

El rol de aplicación (`admin`/`operador`/`viewer`) se obtiene de `GET /api/me`.
`viewer` = **solo lectura**: ve todo pero los controles de edición se ocultan/deshabilitan
(`AuthService.puedeEditar()`); las rutas de edición pueden además protegerse con `editorGuard`.
