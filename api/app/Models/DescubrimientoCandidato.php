<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/** Equipo detectado en un barrido: para dar de alta o descartar. */
class DescubrimientoCandidato extends Model
{
    protected $table = 'descubrimiento_candidatos';

    const UPDATED_AT = null;

    protected $fillable = [
        'escaneo_id', 'ip', 'sysname', 'sysdescr', 'sysobjectid',
        'tipo_sugerido', 'responde_snmp', 'latencia_ms', 'estado', 'recurso_id',
    ];

    protected $casts = [
        'responde_snmp' => 'boolean',
        'latencia_ms'   => 'integer',
        'created_at'    => 'datetime',
    ];

    public function escaneo(): BelongsTo
    {
        return $this->belongsTo(DescubrimientoEscaneo::class, 'escaneo_id');
    }

    public function recurso(): BelongsTo
    {
        return $this->belongsTo(Recurso::class, 'recurso_id');
    }
}
