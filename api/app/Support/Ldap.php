<?php

namespace App\Support;

use Illuminate\Support\Facades\DB;

/**
 * Autenticación contra Active Directory / LDAP por "bind" simple. Tras un bind
 * exitoso, busca el nombre del usuario (displayName/cn) para mostrarlo en SIMON.
 *
 * Ajustes desde app_config (clave 'ldap', editable por UI) con respaldo en
 * config/ldap.php (.env).
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
            'base_dn'      => (string) config('ldap.base_dn', ''),
            'group_dn'     => (string) config('ldap.group_dn', ''),
            'auto_create'  => (bool) config('ldap.auto_create', true),
        ];

        try {
            $row = DB::table('app_config')->where('clave', 'ldap')->value('valor');
        } catch (\Throwable $e) {
            $row = null;
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

    /** Solo verifica credenciales (para la prueba de conexión). */
    public static function autenticarCon(array $a, string $usuario, string $password): bool
    {
        return self::autenticarConDatos($a, $usuario, $password) !== null;
    }

    /**
     * Verifica credenciales y, si son válidas, devuelve los datos del usuario:
     * ['nombre' => displayName|cn|null]. Devuelve null si la autenticación falla.
     */
    public static function autenticarConDatos(array $a, string $usuario, string $password): ?array
    {
        if ($password === '' || ! self::disponible() || empty($a['host'])) {
            return null;
        }

        if (empty($a['tls_verify']) && defined('LDAP_OPT_X_TLS_REQUIRE_CERT')) {
            @ldap_set_option(null, LDAP_OPT_X_TLS_REQUIRE_CERT, LDAP_OPT_X_TLS_NEVER);
        }

        $conn = @ldap_connect($a['host'], (int) ($a['port'] ?? 389));
        if (! $conn) {
            return null;
        }
        ldap_set_option($conn, LDAP_OPT_PROTOCOL_VERSION, 3);
        ldap_set_option($conn, LDAP_OPT_REFERRALS, 0);
        ldap_set_option($conn, LDAP_OPT_NETWORK_TIMEOUT, 5);
        if (! empty($a['use_tls'])) {
            @ldap_start_tls($conn);
        }

        $patron = (string) ($a['bind_pattern'] ?? '{user}');
        $dn = str_replace('{user}', $usuario, $patron);

        if (! @ldap_bind($conn, $dn, $password)) {
            @ldap_unbind($conn);

            return null;
        }

        $base = trim((string) ($a['base_dn'] ?? '')) ?: self::baseDnDesdePatron($patron);

        // Restricción por grupo de AD (si está configurada): debe ser miembro.
        $grupo = trim((string) ($a['group_dn'] ?? ''));
        if ($grupo !== '') {
            if (! $base || ! self::esMiembro($conn, $base, $usuario, $dn, $grupo)) {
                @ldap_unbind($conn);

                return null; // credenciales válidas pero NO autorizado
            }
        }

        $nombre = self::buscarNombre($conn, $base, $usuario, $dn);
        @ldap_unbind($conn);

        return ['nombre' => $nombre];
    }

    /** ¿El usuario es miembro (incl. grupos anidados) del grupo DN dado? */
    private static function esMiembro($conn, string $base, string $usuario, string $dn, string $grupoDn): bool
    {
        $upn = ldap_escape($dn, '', LDAP_ESCAPE_FILTER);
        $sam = ldap_escape($usuario, '', LDAP_ESCAPE_FILTER);
        $g = ldap_escape($grupoDn, '', LDAP_ESCAPE_FILTER);
        // 1.2.840.113556.1.4.1941 = LDAP_MATCHING_RULE_IN_CHAIN (membresía recursiva en AD).
        $filtro = "(&(|(userPrincipalName=$upn)(sAMAccountName=$sam))(memberOf:1.2.840.113556.1.4.1941:=$g))";

        $sr = @ldap_search($conn, $base, $filtro, ['cn']);
        if (! $sr) {
            return false;
        }
        $e = @ldap_get_entries($conn, $sr);

        return ! empty($e['count']);
    }

    /** Busca displayName/cn del usuario en el directorio (best-effort). */
    private static function buscarNombre($conn, ?string $base, string $usuario, string $dn): ?string
    {
        if (! $base) {
            return null;
        }
        $upn = ldap_escape($dn, '', LDAP_ESCAPE_FILTER);
        $sam = ldap_escape($usuario, '', LDAP_ESCAPE_FILTER);
        $filtro = "(|(userPrincipalName=$upn)(sAMAccountName=$sam))";

        $sr = @ldap_search($conn, $base, $filtro, ['displayname', 'cn']);
        if (! $sr) {
            return null;
        }
        $e = @ldap_get_entries($conn, $sr);
        if (empty($e[0])) {
            return null;
        }

        return $e[0]['displayname'][0] ?? $e[0]['cn'][0] ?? null;
    }

    /** Deriva la base DN del sufijo de dominio del patrón ({user}@pnnc.local -> DC=pnnc,DC=local). */
    private static function baseDnDesdePatron(string $patron): ?string
    {
        $pos = strpos($patron, '@');
        if ($pos === false) {
            return null;
        }
        $dom = trim(substr($patron, $pos + 1));
        if ($dom === '') {
            return null;
        }

        return 'DC='.implode(',DC=', explode('.', $dom));
    }
}
