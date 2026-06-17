<?php

namespace App\Models;

use App\Models\Concerns\TieneSecretos;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * Trabajo de barrido de red (auto-descubrimiento). Lo crea la API (en estado
 * 'pendiente') y lo ejecuta el worker: ping sweep + SNMP sysDescr/sysObjectID.
 * La community SNMP viaja cifrada en `secretos` (pgcrypto), nunca se serializa.
 */
class DescubrimientoEscaneo extends Model
{
    use TieneSecretos;

    protected $table = 'descubrimiento_escaneos';

    const UPDATED_AT = null;

    protected $fillable = ['subred', 'snmp_version', 'perfil_id'];

    protected $hidden = ['secretos'];

    protected $casts = [
        'total_vivos'      => 'integer',
        'total_candidatos' => 'integer',
        'created_at'       => 'datetime',
        'completado_at'    => 'datetime',
    ];

    public function candidatos(): HasMany
    {
        return $this->hasMany(DescubrimientoCandidato::class, 'escaneo_id');
    }
}
