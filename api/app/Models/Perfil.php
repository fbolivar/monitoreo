<?php

namespace App\Models;

use Illuminate\Foundation\Auth\User as Authenticatable;

/**
 * Perfil de usuario. `id` es un uuid local; el JWT propio (auth.jwt) resuelve el
 * perfil por su claim `sub`. Autenticación 100% local (sin Supabase).
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
        // El secreto TOTP se cifra en reposo (AES-256, clave APP_KEY del .env) para
        // que un dump de la BD no exponga los secretos 2FA. Transparente: el cast
        // descifra al leer (login/verificación) y cifra al guardar.
        'totp_secret' => 'encrypted',
    ];

    public const ROLES = ['admin', 'operador', 'viewer'];

    public function esAdmin(): bool
    {
        return $this->rol === 'admin';
    }
}
