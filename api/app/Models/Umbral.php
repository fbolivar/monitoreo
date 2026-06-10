<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Umbral extends Model
{
    protected $table = 'umbrales';

    protected $fillable = [
        'recurso_id', 'tipo_id', 'metrica', 'operador',
        'valor_warning', 'valor_critical', 'duracion_segundos', 'activo',
    ];

    protected $casts = [
        'valor_warning'     => 'float',
        'valor_critical'    => 'float',
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
