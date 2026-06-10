# api/ — REST API (PHP + Laravel 11)

API REST de gestión del Sistema de Monitoreo. Única capa que habla con
PostgreSQL. Valida el JWT de Supabase Auth y resuelve el rol del usuario.

> **FASE 2 = solo gestión.** Aún no hay monitoreo activo (eso es FASE 4, los
> workers Python). Aquí: auth, CRUD de configuración y lectura de telemetría.

## Puesta en marcha

Requiere PHP 8.2+ y Composer.

```bash
cd api
composer install
cp .env.example .env
php artisan key:generate

# Ajusta en .env:
#   DB_*               -> Postgres local (docker compose de /infra) o Supabase
#   APP_CRYPTO_KEY     -> MISMA clave con la que se cifró el seed en /infra
#   SUPABASE_JWT_SECRET-> Settings > API > JWT Secret de tu proyecto Supabase

php artisan serve         # http://localhost:8000
php artisan route:list    # ver el ruteo (tabla esperada más abajo)
```

> El esquema lo gestionan las migraciones SQL de `/db` (no las de Laravel).
> Levanta primero la BD: `cd ../infra && docker compose up -d`.

## Autenticación y roles

- **Middleware `supabase.jwt`** ([VerifySupabaseJwt](app/Http/Middleware/VerifySupabaseJwt.php)):
  verifica firma (HS256) + expiración + audiencia del JWT de Supabase, extrae el
  `sub` (uuid) y resuelve el `perfil` local (tabla `perfiles`) con su `rol`.
- **Middleware `role:...`** ([EnsureRole](app/Http/Middleware/EnsureRole.php)):
  autorización por rol.

| Rol | Permisos |
|---|---|
| `admin` | Todo, incluida la gestión de usuarios (`/usuarios`). |
| `operador` | CRUD de configuración de monitoreo. **No** toca usuarios. |
| `viewer` (lectura) | Solo lectura. No escribe nada. |

Enviar el token en cada petición: `Authorization: Bearer <jwt_de_supabase>`.

## Cifrado de secretos (transparente)

Los secretos de `recursos` y `canales_notificacion` se guardan **cifrados**
(pgcrypto AES-256) en la columna `secretos` y **nunca** se devuelven en JSON
(están en `$hidden`). Se manejan vía el trait
[TieneSecretos](app/Models/Concerns/TieneSecretos.php):

```php
$recurso->setSecretosPlanos(['snmp_community' => 'xxx']); // set
$recurso->save();                                          // cifra al persistir
$recurso->secretosDescifrados();                           // lee descifrado (bajo demanda)
```

En las peticiones, los secretos entran por el campo `secretos` (objeto JSON) en
POST/PUT/PATCH; en las respuestas, `show` informa `tiene_secretos: true|false`
pero jamás el contenido. La clave maestra (`APP_CRYPTO_KEY`) vive solo en `.env`.

## Tests

```bash
# Crea una BD de pruebas con el esquema aplicado:
createdb monitoreo_test   # o vía docker
psql "$DATABASE_URL_TEST" -f ../db/migrations/0001_init.up.sql
psql "$DATABASE_URL_TEST" -v app_crypto_key="test-crypto-key-monitoreo" -f ../db/migrations/0002_timeseries.up.sql

php artisan test
```

Cubren: rechazo sin token / token inválido / usuario inactivo, lectura vs
escritura por rol, `operador` sin acceso a usuarios, **secretos nunca en JSON**
+ cifrado/descifrado correcto, y filtros de `metricas`/`chequeos`.
Ver [tests/Feature](tests/Feature).

## Rutas (derivadas de [routes/api.php](routes/api.php))

> Tabla equivalente a `php artisan route:list`. **No ejecutada** (este equipo no
> tiene PHP); generada a mano desde el ruteo. Todas bajo el prefijo `/api` y el
> middleware `supabase.jwt`.

| Método | URI | Acción | Rol requerido |
|---|---|---|---|
| GET | `/api/me` | PerfilController@me | cualquiera |
| GET | `/api/tipos-recurso` | TipoRecursoController@index | cualquiera |
| GET | `/api/tipos-recurso/{id}` | TipoRecursoController@show | cualquiera |
| POST | `/api/tipos-recurso` | TipoRecursoController@store | admin, operador |
| PUT\|PATCH | `/api/tipos-recurso/{id}` | TipoRecursoController@update | admin, operador |
| DELETE | `/api/tipos-recurso/{id}` | TipoRecursoController@destroy | admin, operador |
| GET | `/api/sitios` | SitioController@index | cualquiera |
| GET | `/api/sitios/{id}` | SitioController@show | cualquiera |
| POST | `/api/sitios` | SitioController@store | admin, operador |
| PUT\|PATCH | `/api/sitios/{id}` | SitioController@update | admin, operador |
| DELETE | `/api/sitios/{id}` | SitioController@destroy | admin, operador |
| GET | `/api/recursos` | RecursoController@index | cualquiera |
| GET | `/api/recursos/{id}` | RecursoController@show | cualquiera |
| POST | `/api/recursos` | RecursoController@store | admin, operador |
| PUT\|PATCH | `/api/recursos/{id}` | RecursoController@update | admin, operador |
| DELETE | `/api/recursos/{id}` | RecursoController@destroy | admin, operador |
| GET | `/api/umbrales` | UmbralController@index | cualquiera |
| GET | `/api/umbrales/{id}` | UmbralController@show | cualquiera |
| POST | `/api/umbrales` | UmbralController@store | admin, operador |
| PUT\|PATCH | `/api/umbrales/{id}` | UmbralController@update | admin, operador |
| DELETE | `/api/umbrales/{id}` | UmbralController@destroy | admin, operador |
| GET | `/api/mantenimientos` | MantenimientoController@index | cualquiera |
| GET | `/api/mantenimientos/{id}` | MantenimientoController@show | cualquiera |
| POST | `/api/mantenimientos` | MantenimientoController@store | admin, operador |
| PUT\|PATCH | `/api/mantenimientos/{id}` | MantenimientoController@update | admin, operador |
| DELETE | `/api/mantenimientos/{id}` | MantenimientoController@destroy | admin, operador |
| GET | `/api/canales-notificacion` | CanalNotificacionController@index | cualquiera |
| GET | `/api/canales-notificacion/{id}` | CanalNotificacionController@show | cualquiera |
| POST | `/api/canales-notificacion` | CanalNotificacionController@store | admin, operador |
| PUT\|PATCH | `/api/canales-notificacion/{id}` | CanalNotificacionController@update | admin, operador |
| DELETE | `/api/canales-notificacion/{id}` | CanalNotificacionController@destroy | admin, operador |
| GET | `/api/chequeos` | ChequeoController@index | cualquiera (RO) |
| GET | `/api/chequeos/{id}` | ChequeoController@show | cualquiera (RO) |
| GET | `/api/metricas` | MetricaController@index | cualquiera (RO) |
| GET | `/api/incidencias` | IncidenciaController@index | cualquiera (RO) |
| GET | `/api/incidencias/{id}` | IncidenciaController@show | cualquiera (RO) |
| GET | `/api/usuarios` | PerfilController@index | **admin** |
| GET | `/api/usuarios/{id}` | PerfilController@show | **admin** |
| POST | `/api/usuarios` | PerfilController@store | **admin** |
| PUT\|PATCH | `/api/usuarios/{id}` | PerfilController@update | **admin** |

### Filtros de los endpoints de lectura

- `GET /api/chequeos` — `recurso_id`, `estado`, `desde`, `hasta`, `per_page`
- `GET /api/metricas` — `recurso_id`, `metrica`, `desde`, `hasta`, `per_page`
- `GET /api/incidencias` — `recurso_id`, `estado`, `severidad`, `desde`, `hasta`, `per_page`
- `GET /api/recursos` — `tipo_id`, `sitio_id`, `estado`, `activo`, `buscar`, `per_page`
