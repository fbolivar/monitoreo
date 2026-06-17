<?php

use App\Http\Controllers\AuditoriaController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\CanalNotificacionController;
use App\Http\Controllers\ChequeoController;
use App\Http\Controllers\ConfigLdapController;
use App\Http\Controllers\DescubrimientoController;
use App\Http\Controllers\DosFactorController;
use App\Http\Controllers\IncidenciaController;
use App\Http\Controllers\MantenimientoController;
use App\Http\Controllers\MetricaController;
use App\Http\Controllers\PerfilController;
use App\Http\Controllers\PronosticoController;
use App\Http\Controllers\RecursoController;
use App\Http\Controllers\ReglaController;
use App\Http\Controllers\ReporteController;
use App\Http\Controllers\ReporteExportController;
use App\Http\Controllers\ReporteProgramadoController;
use App\Http\Controllers\ServicioController;
use App\Http\Controllers\SitioController;
use App\Http\Controllers\TrapController;
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
    'reglas'               => ReglaController::class,
    'reportes-programados' => ReporteProgramadoController::class,
    'servicios'            => ServicioController::class,
    'mantenimientos'       => MantenimientoController::class,
    'canales-notificacion' => CanalNotificacionController::class,
];

Route::middleware('auth.jwt')->group(function () use ($crud) {

    // Perfil propio (cualquier rol).
    Route::get('me', [PerfilController::class, 'me']);

    // 2FA (TOTP) del usuario autenticado.
    Route::post('2fa/iniciar', [DosFactorController::class, 'iniciar']);
    Route::post('2fa/activar', [DosFactorController::class, 'activar']);
    Route::post('2fa/desactivar', [DosFactorController::class, 'desactivar']);

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

    // Exportación de reportes (ejecutivo/sitio/recurso/servicios) en CSV/XLSX/PDF.
    Route::get('reportes/export/{tipo}', [ReporteExportController::class, 'export'])
        ->whereIn('tipo', ['ejecutivo', 'sitio', 'recurso', 'servicios']);

    // Pronósticos de capacidad (lectura): los calcula el worker.
    Route::get('pronosticos', [PronosticoController::class, 'index']);

    // Línea base estacional / anomalías de un recurso (lectura).
    Route::get('recursos/{id}/baselines', [RecursoController::class, 'baselines'])->whereNumber('id');

    // Hardware físico (Redfish/IPMI) de un recurso: inventario + componentes (lectura).
    Route::get('recursos/{id}/hardware', [RecursoController::class, 'hardware'])->whereNumber('id');

    // Observabilidad de servicios: analisis de correlacion de una transaccion.
    Route::get('servicios/{id}/analisis', [ServicioController::class, 'analisis'])->whereNumber('id');

    // SNMP traps recibidos (lectura).
    Route::get('traps', [TrapController::class, 'index']);

    // Auto-descubrimiento de red (lectura): escaneos y candidatos.
    Route::get('descubrimiento', [DescubrimientoController::class, 'index']);
    Route::get('descubrimiento/tipos', [DescubrimientoController::class, 'tiposSugeridos']);
    Route::get('descubrimiento/{id}', [DescubrimientoController::class, 'show'])->whereNumber('id');

    // Respaldos de configuración de un recurso (lectura).
    Route::get('recursos/{id}/respaldos', [RecursoController::class, 'respaldos'])->whereNumber('id');
    Route::get('recursos/{id}/respaldos/{respaldoId}', [RecursoController::class, 'respaldoContenido'])
        ->whereNumber('id')->whereNumber('respaldoId');

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

        // Auto-descubrimiento: encolar barrido, alta/descartar candidatos.
        Route::post('descubrimiento', [DescubrimientoController::class, 'store']);
        Route::delete('descubrimiento/{id}', [DescubrimientoController::class, 'destroy'])->whereNumber('id');
        Route::post('descubrimiento/candidatos/{candidatoId}/agregar',
            [DescubrimientoController::class, 'agregar'])->whereNumber('candidatoId');
        Route::post('descubrimiento/candidatos/{candidatoId}/descartar',
            [DescubrimientoController::class, 'descartar'])->whereNumber('candidatoId');
    });

    // ── USUARIOS (perfiles) y AUDITORÍA: solo admin ──────────────────
    Route::middleware('role:admin')->group(function () {
        Route::get('auditoria', [AuditoriaController::class, 'index']);

        // Configuración de SSO LDAP/AD.
        Route::get('config/ldap', [ConfigLdapController::class, 'mostrar']);
        Route::match(['put', 'patch'], 'config/ldap', [ConfigLdapController::class, 'guardar']);
        Route::post('config/ldap/probar', [ConfigLdapController::class, 'probar']);

        Route::get('usuarios', [PerfilController::class, 'index']);
        Route::get('usuarios/{id}', [PerfilController::class, 'show']);
        Route::post('usuarios', [PerfilController::class, 'store']);
        Route::match(['put', 'patch'], 'usuarios/{id}', [PerfilController::class, 'update']);
        Route::delete('usuarios/{id}', [PerfilController::class, 'destroy']);
    });
});
