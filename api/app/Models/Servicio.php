<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Servicio extends Model
{
    protected $table = 'servicios';

    protected $fillable = [
        'nombre', 'descripcion', 'objetivo_ms', 'impacto_negocio', 'activo',
    ];

    protected $casts = [
        'objetivo_ms' => 'integer',
        'activo'      => 'boolean',
    ];

    public function componentes(): HasMany
    {
        return $this->hasMany(ServicioComponente::class, 'servicio_id')->orderBy('orden');
    }
}
