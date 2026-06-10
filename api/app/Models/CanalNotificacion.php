<?php

namespace App\Models;

use App\Models\Concerns\TieneSecretos;
use Illuminate\Database\Eloquent\Model;

class CanalNotificacion extends Model
{
    use TieneSecretos;

    protected $table = 'canales_notificacion';

    protected $fillable = ['tipo', 'nombre', 'config', 'activo'];

    protected $hidden = ['secretos'];

    protected $casts = [
        'config' => 'array',
        'activo' => 'boolean',
    ];

    protected $attributes = [
        'config' => '{}',
    ];
}
