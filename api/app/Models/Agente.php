<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Agente extends Model
{
    public $timestamps = false;

    protected $table = 'agentes';

    protected $fillable = ['recurso_id', 'nombre', 'token_hash', 'hostname', 'so', 'version', 'activo'];

    protected $hidden = ['token_hash'];

    protected $casts = [
        'activo' => 'boolean',
        'inventario' => 'array',
        'last_seen' => 'datetime',
    ];
}
