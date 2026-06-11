<?php

namespace App\Support;

/**
 * Autenticación contra Active Directory / LDAP por "bind" simple: si el bind con
 * las credenciales del usuario tiene éxito, la contraseña es válida.
 * Env-gated (config/ldap.php). Si la extensión php-ldap no está, se desactiva.
 */
class Ldap
{
    public static function habilitado(): bool
    {
        return (bool) config('ldap.enabled') && function_exists('ldap_connect');
    }

    public static function autenticar(string $usuario, string $password): bool
    {
        if ($password === '' || ! self::habilitado()) {
            return false;
        }

        $host = config('ldap.host');
        $port = (int) config('ldap.port', 389);
        if (! $host) {
            return false;
        }

        $conn = @ldap_connect($host, $port);
        if (! $conn) {
            return false;
        }
        ldap_set_option($conn, LDAP_OPT_PROTOCOL_VERSION, 3);
        ldap_set_option($conn, LDAP_OPT_REFERRALS, 0);
        ldap_set_option($conn, LDAP_OPT_NETWORK_TIMEOUT, 5);
        if (config('ldap.use_tls')) {
            @ldap_start_tls($conn);
        }

        $dn = str_replace('{user}', $usuario, (string) config('ldap.bind_pattern', '{user}'));
        $ok = @ldap_bind($conn, $dn, $password);
        @ldap_unbind($conn);

        return (bool) $ok;
    }
}
