<?php

namespace App\Providers;

use App\Models\CanalNotificacion;
use App\Models\Incidencia;
use App\Models\Mantenimiento;
use App\Models\Perfil;
use App\Models\Recurso;
use App\Models\Regla;
use App\Models\ReporteProgramado;
use App\Models\Servicio;
use App\Models\Sitio;
use App\Models\TipoRecurso;
use App\Models\Umbral;
use App\Observers\AuditObserver;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        // Bitácora de auditoría: observa el CRUD de las entidades de gestión.
        foreach ([
            Recurso::class, Sitio::class, TipoRecurso::class, Umbral::class,
            Mantenimiento::class, CanalNotificacion::class, Perfil::class, Incidencia::class,
            Regla::class, ReporteProgramado::class, Servicio::class,
        ] as $modelo) {
            $modelo::observe(AuditObserver::class);
        }
    }
}
