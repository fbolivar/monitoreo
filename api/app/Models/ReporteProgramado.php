<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class ReporteProgramado extends Model
{
    protected $table = 'reportes_programados';

    protected $fillable = [
        'nombre', 'periodo', 'rango', 'destinatarios', 'formato', 'activo',
        // Filtro opcional del informe (NULL = todos): permite acotarlo a una
        // audiencia sin exponer el resto de la infraestructura.
        'tipo_id', 'sitio_id',
    ];

    protected $casts = [
        'activo'          => 'boolean',
        'ultimo_envio_at' => 'datetime',
    ];
}
