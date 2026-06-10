<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class TipoRecurso extends Model
{
    protected $table = 'tipos_recurso';

    // La tabla solo tiene created_at.
    const UPDATED_AT = null;

    protected $fillable = ['codigo', 'nombre', 'descripcion', 'protocolo_default', 'icono'];

    public function recursos(): HasMany
    {
        return $this->hasMany(Recurso::class, 'tipo_id');
    }

    public function umbrales(): HasMany
    {
        return $this->hasMany(Umbral::class, 'tipo_id');
    }
}
