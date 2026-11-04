<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Incidencia extends Model
{
    protected $table = 'incidencias';

    protected $fillable = [
        'recurso_id', 'estado', 'severidad', 'titulo', 'descripcion',
        'chequeo_apertura_id', 'abierta_at', 'reconocida_at', 'reconocida_por', 'resuelta_at',
        'asignado_a', 'silenciado_hasta',
    ];

    protected $casts = [
        'abierta_at'       => 'datetime',
        'reconocida_at'    => 'datetime',
        'resuelta_at'      => 'datetime',
        'silenciado_hasta' => 'datetime',
    ];

    public function recurso(): BelongsTo
    {
        return $this->belongsTo(Recurso::class, 'recurso_id');
    }

    public function reconocidaPor(): BelongsTo
    {
        return $this->belongsTo(Perfil::class, 'reconocida_por');
    }

    /** Operador asignado. Se llama 'operador' (no 'asignadoA') para que su clave en
     *  el JSON no colisione con la columna uuid `asignado_a`. */
    public function operador(): BelongsTo
    {
        return $this->belongsTo(Perfil::class, 'asignado_a');
    }
}
