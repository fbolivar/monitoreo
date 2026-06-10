<?php

namespace App\Http\Middleware;

use App\Models\Perfil;
use Closure;
use Firebase\JWT\JWT;
use Firebase\JWT\Key;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Valida el JWT propio de la aplicación (emitido por AuthController) y resuelve
 * el perfil/rol local. Autenticación 100% local (sin Supabase).
 */
class VerifyJwt
{
    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->bearerToken();
        if (! $token) {
            return response()->json(['message' => 'Token de autenticación ausente.'], 401);
        }

        $secret = config('auth_local.jwt_secret');
        if (! $secret) {
            return response()->json(['message' => 'AUTH_JWT_SECRET no configurado.'], 500);
        }

        try {
            JWT::$leeway = (int) config('auth_local.leeway', 30);
            $payload = JWT::decode($token, new Key($secret, 'HS256'));
        } catch (\Throwable $e) {
            return response()->json(['message' => 'Token inválido o expirado.'], 401);
        }

        $sub = $payload->sub ?? null;
        if (! $sub) {
            return response()->json(['message' => 'Token sin identificador de usuario.'], 401);
        }

        $perfil = Perfil::find($sub);
        if (! $perfil) {
            return response()->json(['message' => 'Usuario no encontrado.'], 403);
        }
        if (! $perfil->activo) {
            return response()->json(['message' => 'Usuario desactivado.'], 403);
        }

        $request->attributes->set('perfil', $perfil);
        $request->setUserResolver(fn () => $perfil);

        return $next($request);
    }
}
