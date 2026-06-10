<?php

use App\Http\Controllers\CanalNotificacionController;
use App\Http\Controllers\ChequeoController;
use App\Http\Controllers\IncidenciaController;
use App\Http\Controllers\MantenimientoController;
use App\Http\Controllers\MetricaController;
use App\Http\Controllers\PerfilController;
use App\Http\Controllers\RecursoController;
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
|   - GET (lectura)            -> cualquier rol autenticado (admin/operador/viewer)
|   - POST/PUT/PATCH/DELETE de configuración -> admin, operador
|   - /usuarios (gestión de perfiles)        -> solo admin
*/

// Recursos de configuración con CRUD completo.
$crud = [
    'tipos-recurso'        => TipoRecursoController::class,
    'sitios'               => SitioController::class,
    'recursos'             => RecursoController::class,
    'umbrales'             => UmbralController::class,
    'mantenimientos'       => MantenimientoController::class,
    'canales-notificacion' => CanalNotificacionController::class,
];

Route::middleware('supabase.jwt')->group(function () use ($crud) {

    // Perfil propio (cualquier rol).
    Route::get('me', [PerfilController::class, 'me']);

    // ── LECTURA: cualquier rol autenticado ───────────────────────────
    foreach ($crud as $uri => $controller) {
        Route::get($uri, [$controller, 'index']);
        Route::get($uri.'/{id}', [$controller, 'show'])->whereNumber('id');
    }

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
    });

    // ── USUARIOS (perfiles): solo admin ──────────────────────────────
    Route::middleware('role:admin')->group(function () {
        Route::get('usuarios', [PerfilController::class, 'index']);
        Route::get('usuarios/{id}', [PerfilController::class, 'show']);
        Route::post('usuarios', [PerfilController::class, 'store']);
        Route::match(['put', 'patch'], 'usuarios/{id}', [PerfilController::class, 'update']);
    });
});
