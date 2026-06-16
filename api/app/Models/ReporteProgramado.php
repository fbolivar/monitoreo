<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class ReporteProgramado extends Model
{
    protected $table = 'reportes_programados';

    protected $fillable = [
        'nombre', 'periodo', 'rango', 'destinatarios', 'formato', 'activo',
    ];

    protected $casts = [
        'activo'          => 'boolean',
        'ultimo_envio_at' => 'datetime',
    ];
}
