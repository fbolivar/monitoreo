<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ServicioComponente extends Model
{
    protected $table = 'servicio_componentes';

    protected $fillable = [
        'servicio_id', 'orden', 'nombre', 'tipo', 'recurso_id', 'umbral_ms',
    ];

    protected $casts = [
        'orden'     => 'integer',
        'umbral_ms' => 'integer',
    ];

    public function servicio(): BelongsTo
    {
        return $this->belongsTo(Servicio::class, 'servicio_id');
    }

    public function recurso(): BelongsTo
    {
        return $this->belongsTo(Recurso::class, 'recurso_id');
    }
}
