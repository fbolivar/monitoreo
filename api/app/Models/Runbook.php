<?php

namespace App\Models;

use App\Models\Concerns\TieneSecretos;
use Illuminate\Database\Eloquent\Model;

class Runbook extends Model
{
    use TieneSecretos;

    protected $table = 'runbooks';

    protected $fillable = [
        'nombre', 'descripcion', 'activo', 'trigger_tipo_id', 'trigger_severidad',
        'trigger_match', 'accion', 'cooldown_seg',
    ];

    protected $hidden = ['secretos'];

    protected $casts = [
        'activo' => 'boolean',
        'accion' => 'array',
        'cooldown_seg' => 'integer',
    ];

    protected $attributes = [
        'accion' => '{}',
    ];
}
