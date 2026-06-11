<?php

namespace App\Http\Controllers;

use App\Support\Auditoria;
use App\Support\Ldap;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/** Configuración de SSO LDAP/AD desde la UI (solo admin). */
class ConfigLdapController extends Controller
{
    public function mostrar(): JsonResponse
    {
        return response()->json([
            'config'     => Ldap::ajustes(),
            'disponible' => Ldap::disponible(), // ¿extensión php-ldap instalada?
        ]);
    }

    public function guardar(Request $request): JsonResponse
    {
        $data = $request->validate([
            'enabled'      => ['required', 'boolean'],
            'host'         => ['nullable', 'string', 'max:255'],
            'port'         => ['nullable', 'integer', 'between:1,65535'],
            'use_tls'      => ['boolean'],
            'bind_pattern' => ['nullable', 'string', 'max:255'],
            'rol_default'  => ['nullable', 'in:admin,operador,viewer'],
        ]);

        if ($data['enabled'] && empty($data['host'])) {
            return response()->json(['message' => 'Para activar LDAP debes indicar el host.'], 422);
        }

        $valor = [
            'enabled'      => (bool) $data['enabled'],
            'host'         => $data['host'] ?? null,
            'port'         => (int) ($data['port'] ?? 389),
            'use_tls'      => (bool) ($data['use_tls'] ?? false),
            'bind_pattern' => $data['bind_pattern'] ?? '{user}',
            'rol_default'  => $data['rol_default'] ?? 'viewer',
        ];

        DB::table('app_config')->updateOrInsert(
            ['clave' => 'ldap'],
            ['valor' => json_encode($valor, JSON_UNESCAPED_UNICODE), 'updated_at' => now()],
        );

        Auditoria::registrar('actualizar', 'app_config', 'ldap', 'Configuración LDAP',
            ['enabled' => [null, $valor['enabled']], 'host' => [null, $valor['host']]]);

        return response()->json($valor);
    }

    /** Prueba de conexión: intenta autenticar un usuario con los ajustes dados. */
    public function probar(Request $request): JsonResponse
    {
        $data = $request->validate([
            'host'          => ['required', 'string'],
            'port'          => ['nullable', 'integer'],
            'use_tls'       => ['boolean'],
            'bind_pattern'  => ['nullable', 'string'],
            'test_usuario'  => ['required', 'string'],
            'test_password' => ['required', 'string'],
        ]);

        if (! Ldap::disponible()) {
            return response()->json(['ok' => false, 'mensaje' => 'La extensión php-ldap no está instalada en el servidor.']);
        }

        $ajustes = [
            'host'         => $data['host'],
            'port'         => $data['port'] ?? 389,
            'use_tls'      => (bool) ($data['use_tls'] ?? false),
            'bind_pattern' => $data['bind_pattern'] ?? '{user}',
        ];

        $ok = Ldap::autenticarCon($ajustes, $data['test_usuario'], $data['test_password']);

        return response()->json([
            'ok'      => $ok,
            'mensaje' => $ok
                ? 'Conexión y autenticación correctas. El usuario de prueba pudo autenticarse.'
                : 'No se pudo autenticar. Revisa host/puerto, el patrón de bind y las credenciales de prueba.',
        ]);
    }
}
