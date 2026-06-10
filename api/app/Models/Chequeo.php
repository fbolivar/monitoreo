<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Chequeo extends Model
{
    protected $table = 'chequeos';

    // Serie de eventos: usa `ts`, sin created_at/updated_at.
    public $timestamps = false;

    protected $fillable = ['recurso_id', 'ts', 'estado', 'latencia_ms', 'detalle'];

    protected $casts = [
        'ts'          => 'datetime',
        'latencia_ms' => 'integer',
        'detalle'     => 'array',
    ];

    public function recurso(): BelongsTo
    {
        return $this->belongsTo(Recurso::class, 'recurso_id');
    }
}
