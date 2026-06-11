<?php

namespace App\Http\Controllers;

use App\Models\Perfil;
use App\Support\Auditoria;
use App\Support\Ldap;
use App\Support\Totp;
use Firebase\JWT\JWT;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Str;

/**
 * Autenticación LOCAL: verifica email + contraseña (bcrypt en `perfiles`) y
 * emite un JWT propio (HS256) firmado con AUTH_JWT_SECRET. Sin Supabase.
 */
class AuthController extends Controller
{
    public function login(Request $request): JsonResponse
    {
        $data = $request->validate([
            // Acepta correo (cuentas locales) o usuario corto (SSO LDAP/AD).
            'email'    => ['required', 'string', 'max:255'],
            'password' => ['required', 'string'],
            'codigo'   => ['nullable', 'string'],   // código TOTP (2FA)
        ]);

        $perfil = Perfil::where('email', $data['email'])->first();

        // 1) Autenticación local (contraseña en perfiles).
        $autenticado = $perfil
            && $perfil->activo
            && $perfil->origen === 'local'
            && $perfil->password_hash
            && Hash::check($data['password'], $perfil->password_hash);

        // 2) SSO LDAP/AD (si está habilitado): usuarios sin perfil local o de origen ldap.
        if (! $autenticado && Ldap::habilitado()
            && (! $perfil || $perfil->origen === 'ldap' || ! $perfil->password_hash)) {
            $ajustes = Ldap::ajustes();
            $datos = Ldap::autenticarConDatos($ajustes, $data['email'], $data['password']);
            if ($datos !== null) {
                $autenticado = true;
                $nombre = $datos['nombre'] ?: $data['email'];
                if (! $perfil) {
                    $perfil = Perfil::create([
                        'id'     => (string) Str::uuid(),
                        'email'  => $data['email'],
                        'nombre' => $nombre,
                        'rol'    => $ajustes['rol_default'] ?? 'viewer',
                        'activo' => true,
                        'origen' => 'ldap',
                    ]);
                } elseif ($datos['nombre'] && $perfil->nombre !== $datos['nombre']) {
                    // Mantener el nombre sincronizado con el directorio.
                    $perfil->nombre = $datos['nombre'];
                    $perfil->save();
                }
            }
        }

        if (! $autenticado || ! $perfil || ! $perfil->activo) {
            Auditoria::registrar('login_fallido', 'auth', null, $data['email']);

            return response()->json(['message' => 'Credenciales inválidas.'], 401);
        }

        // 3) Segundo factor (TOTP) para perfiles que lo tengan activo.
        if ($perfil->totp_activo) {
            $codigo = $data['codigo'] ?? null;
            if (! $codigo) {
                return response()->json(['requiere_2fa' => true], 200);
            }
            if (! Totp::verificar((string) $perfil->totp_secret, $codigo)) {
                Auditoria::registrar('login_fallido', 'auth', $perfil->id, $perfil->email.' (2FA)');

                return response()->json(['requiere_2fa' => true, 'mensaje' => 'Código 2FA inválido.'], 200);
            }
        }

        $now = time();
        $payload = [
            'sub'   => $perfil->id,
            'email' => $perfil->email,
            'rol'   => $perfil->rol,
            'iat'   => $now,
            'exp'   => $now + (int) config('auth_local.ttl'),
        ];
        $token = JWT::encode($payload, config('auth_local.jwt_secret'), 'HS256');

        Auditoria::registrar('login', 'auth', $perfil->id, $perfil->email, null, $perfil);

        return response()->json([
            'token'  => $token,
            'perfil' => $perfil,
        ]);
    }
}
