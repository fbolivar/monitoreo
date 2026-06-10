<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Mantenimiento extends Model
{
    protected $table = 'mantenimientos';

    // La tabla solo tiene created_at.
    const UPDATED_AT = null;

    protected $fillable = [
        'recurso_id', 'sitio_id', 'inicio', 'fin', 'motivo', 'creado_por',
    ];

    protected $casts = [
        'inicio' => 'datetime',
        'fin'    => 'datetime',
    ];

    public function recurso(): BelongsTo
    {
        return $this->belongsTo(Recurso::class, 'recurso_id');
    }

    public function sitio(): BelongsTo
    {
        return $this->belongsTo(Sitio::class, 'sitio_id');
    }
}
