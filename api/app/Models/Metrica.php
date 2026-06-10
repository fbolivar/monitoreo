<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Metrica extends Model
{
    protected $table = 'metricas';

    // Tabla particionada con PK compuesta (recurso_id, metrica, ts). Solo lectura
    // desde la API; sin clave autoincremental ni timestamps de Eloquent.
    public $timestamps = false;
    public $incrementing = false;
    protected $primaryKey = null;
    protected $keyType = 'string';

    protected $fillable = ['recurso_id', 'metrica', 'valor', 'unidad', 'ts'];

    protected $casts = [
        'valor' => 'float',
        'ts'    => 'datetime',
    ];

    public function recurso(): BelongsTo
    {
        return $this->belongsTo(Recurso::class, 'recurso_id');
    }
}
