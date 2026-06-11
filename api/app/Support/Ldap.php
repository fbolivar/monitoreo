<?php

namespace App\Support;

use Illuminate\Support\Facades\DB;

/**
 * Autenticación contra Active Directory / LDAP por "bind" simple: si el bind con
 * las credenciales del usuario tiene éxito, la contraseña es válida.
 *
 * Los ajustes salen de la tabla app_config (clave 'ldap'), editable desde la UI,
 * con respaldo en config/ldap.php (.env) para compatibilidad.
 */
class Ldap
{
    /** Ajustes efectivos: BD (UI) por encima de los valores por defecto de .env. */
    public static function ajustes(): array
    {
        $base = [
            'enabled'      => (bool) config('ldap.enabled'),
            'host'         => config('ldap.host'),
            'port'         => (int) config('ldap.port', 389),
            'use_tls'      => (bool) config('ldap.use_tls'),
            'bind_pattern' => (string) config('ldap.bind_pattern', '{user}'),
            'rol_default'  => (string) config('ldap.rol_default', 'viewer'),
        ];

        try {
            $row = DB::table('app_config')->where('clave', 'ldap')->value('valor');
        } catch (\Throwable $e) {
            $row = null; // tabla aún no migrada
        }
        if ($row) {
            $db = is_string($row) ? json_decode($row, true) : (array) $row;
            if (is_array($db)) {
                $base = array_merge($base, array_filter($db, fn ($v) => $v !== null));
            }
        }

        return $base;
    }

    public static function disponible(): bool
    {
        return function_exists('ldap_connect');
    }

    public static function habilitado(): bool
    {
        return self::disponible() && (bool) (self::ajustes()['enabled'] ?? false);
    }

    public static function autenticar(string $usuario, string $password): bool
    {
        if (! self::habilitado()) {
            return false;
        }

        return self::autenticarCon(self::ajustes(), $usuario, $password);
    }

    /** Intenta un bind con los ajustes dados (usado también por la prueba de conexión). */
    public static function autenticarCon(array $a, string $usuario, string $password): bool
    {
        if ($password === '' || ! self::disponible() || empty($a['host'])) {
            return false;
        }

        $conn = @ldap_connect($a['host'], (int) ($a['port'] ?? 389));
        if (! $conn) {
            return false;
        }
        ldap_set_option($conn, LDAP_OPT_PROTOCOL_VERSION, 3);
        ldap_set_option($conn, LDAP_OPT_REFERRALS, 0);
        ldap_set_option($conn, LDAP_OPT_NETWORK_TIMEOUT, 5);
        if (! empty($a['use_tls'])) {
            @ldap_start_tls($conn);
        }

        $dn = str_replace('{user}', $usuario, (string) ($a['bind_pattern'] ?? '{user}'));
        $ok = @ldap_bind($conn, $dn, $password);
        @ldap_unbind($conn);

        return (bool) $ok;
    }
}
