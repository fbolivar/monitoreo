<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class PoliticaCumplimiento extends Model
{
    protected $table = 'cumplimiento_politicas';

    protected $fillable = [
        'nombre', 'descripcion', 'tipo', 'patron', 'severidad', 'aplica_tipo_id', 'activo',
    ];

    protected $casts = [
        'activo' => 'boolean',
    ];
}
