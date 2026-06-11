<?php

namespace App\Models;

use Illuminate\Foundation\Auth\User as Authenticatable;

/**
 * Perfil de usuario. `id` (uuid) coincide con auth.users.id de Supabase, pero
 * sin FK (portabilidad). El JWT de Supabase resuelve el perfil por su `sub`.
 */
class Perfil extends Authenticatable
{
    protected $table = 'perfiles';

    // PK uuid no autoincremental.
    public $incrementing = false;
    protected $keyType = 'string';

    protected $fillable = ['id', 'email', 'nombre', 'rol', 'activo', 'origen', 'totp_activo'];

    // El hash de contraseña y el secreto TOTP nunca se serializan en respuestas JSON.
    protected $hidden = ['password_hash', 'totp_secret'];

    protected $casts = [
        'activo'      => 'boolean',
        'totp_activo' => 'boolean',
    ];

    public const ROLES = ['admin', 'operador', 'viewer'];

    public function esAdmin(): bool
    {
        return $this->rol === 'admin';
    }
}
