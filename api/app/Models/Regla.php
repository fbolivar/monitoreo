<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Regla extends Model
{
    protected $table = 'reglas';

    protected $fillable = [
        'recurso_id', 'tipo_id', 'nombre', 'descripcion',
        'expresion', 'severidad', 'duracion_segundos', 'activo',
    ];

    protected $casts = [
        'expresion'         => 'array',
        'duracion_segundos' => 'integer',
        'activo'            => 'boolean',
    ];

    public function recurso(): BelongsTo
    {
        return $this->belongsTo(Recurso::class, 'recurso_id');
    }

    public function tipo(): BelongsTo
    {
        return $this->belongsTo(TipoRecurso::class, 'tipo_id');
    }
}
