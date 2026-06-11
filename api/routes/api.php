<?php

use App\Http\Controllers\AuditoriaController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\CanalNotificacionController;
use App\Http\Controllers\ChequeoController;
use App\Http\Controllers\IncidenciaController;
use App\Http\Controllers\MantenimientoController;
use App\Http\Controllers\MetricaController;
use App\Http\Controllers\PerfilController;
use App\Http\Controllers\RecursoController;
use App\Http\Controllers\ReporteController;
use App\Http\Controllers\SitioController;
use App\Http\Controllers\TipoRecursoController;
use App\Http\Controllers\UmbralController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API (prefijo /api)  — FASE 2: solo gestión
|--------------------------------------------------------------------------
| Autenticación: middleware 'supabase.jwt' valida el JWT de Supabase y
| resuelve el perfil/rol local. Autorización por rol con 'role:...'.
|
| Matriz de permisos:
|   - POST /api/auth/login     -> público (autenticación local: email + contraseña)
|   - GET (lectura)            -> cualquier rol autenticado (admin/operador/viewer)
|   - POST/PUT/PATCH/DELETE de configuración -> admin, operador
|   - /usuarios (gestión de perfiles)        -> solo admin
*/

// Autenticación local (pública): devuelve un JWT propio.
Route::post('auth/login', [AuthController::class, 'login']);

// Recursos de configuración con CRUD completo.
$crud = [
    'tipos-recurso'        => TipoRecursoController::class,
    'sitios'               => SitioController::class,
    'recursos'             => RecursoController::class,
    'umbrales'             => UmbralController::class,
    'mantenimientos'       => MantenimientoController::class,
    'canales-notificacion' => CanalNotificacionController::class,
];

Route::middleware('auth.jwt')->group(function () use ($crud) {

    // Perfil propio (cualquier rol).
    Route::get('me', [PerfilController::class, 'me']);

    // ── LECTURA: cualquier rol autenticado ───────────────────────────
    foreach ($crud as $uri => $controller) {
        Route::get($uri, [$controller, 'index']);
        Route::get($uri.'/{id}', [$controller, 'show'])->whereNumber('id');
    }

    // Interfaces de red (IF-MIB) de un recurso (lectura).
    Route::get('recursos/{id}/interfaces', [RecursoController::class, 'interfaces'])->whereNumber('id');
    Route::get('recursos/{id}/interfaces/{ifIndex}/historico',
        [RecursoController::class, 'interfazHistorico'])->whereNumber('id')->whereNumber('ifIndex');

    // Reportes (lectura): disponibilidad/SLA por recurso en un periodo.
    Route::get('reportes/disponibilidad', [ReporteController::class, 'disponibilidad']);

    // Solo lectura (telemetría / eventos) con filtros.
    Route::get('chequeos', [ChequeoController::class, 'index']);
    Route::get('chequeos/{id}', [ChequeoController::class, 'show'])->whereNumber('id');
    Route::get('metricas', [MetricaController::class, 'index']);          // sin show (PK compuesta)
    Route::get('incidencias', [IncidenciaController::class, 'index']);
    Route::get('incidencias/{id}', [IncidenciaController::class, 'show'])->whereNumber('id');

    // ── ESCRITURA de configuración: admin + operador ─────────────────
    Route::middleware('role:admin,operador')->group(function () use ($crud) {
        foreach ($crud as $uri => $controller) {
            Route::post($uri, [$controller, 'store']);
            Route::match(['put', 'patch'], $uri.'/{id}', [$controller, 'update'])->whereNumber('id');
            Route::delete($uri.'/{id}', [$controller, 'destroy'])->whereNumber('id');
        }

        // Marcar interfaz como monitoreada (alertar si cae).
        Route::match(['put', 'patch'], 'recursos/{id}/interfaces/{ifIndex}',
            [RecursoController::class, 'actualizarInterfaz'])->whereNumber('id')->whereNumber('ifIndex');

        // Gestión de incidencias (reconocer / resolver).
        Route::post('incidencias/{id}/reconocer', [IncidenciaController::class, 'reconocer'])->whereNumber('id');
        Route::post('incidencias/{id}/resolver', [IncidenciaController::class, 'resolver'])->whereNumber('id');
    });

    // ── USUARIOS (perfiles) y AUDITORÍA: solo admin ──────────────────
    Route::middleware('role:admin')->group(function () {
        Route::get('auditoria', [AuditoriaController::class, 'index']);
        Route::get('usuarios', [PerfilController::class, 'index']);
        Route::get('usuarios/{id}', [PerfilController::class, 'show']);
        Route::post('usuarios', [PerfilController::class, 'store']);
        Route::match(['put', 'patch'], 'usuarios/{id}', [PerfilController::class, 'update']);
    });
});
