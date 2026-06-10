<?php

namespace App\Http\Middleware;

use App\Models\Perfil;
use Closure;
use Firebase\JWT\JWT;
use Firebase\JWT\Key;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Valida el JWT emitido por Supabase Auth (HS256, firmado con el JWT Secret
 * del proyecto). Resuelve el perfil local (tabla `perfiles`) a partir del
 * claim `sub` y lo deja disponible en el request, junto con su rol.
 *
 * No accede a la BD de Supabase: solo verifica firma + expiración y mapea el
 * usuario a su perfil local. La autorización fina la hace EnsureRole.
 */
class VerifySupabaseJwt
{
    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->bearerToken();

        if (! $token) {
            return response()->json(['message' => 'Token de autenticación ausente.'], 401);
        }

        $secret = config('supabase.jwt_secret');
        if (! $secret) {
            return response()->json(['message' => 'JWT secret de Supabase no configurado.'], 500);
        }

        try {
            JWT::$leeway = (int) config('supabase.jwt_leeway', 30);
            $payload = JWT::decode($token, new Key($secret, 'HS256'));
        } catch (\Throwable $e) {
            return response()->json(['message' => 'Token inválido o expirado.'], 401);
        }

        // Validación de audiencia (Supabase: 'authenticated').
        $audEsperada = config('supabase.jwt_audience');
        $aud = $payload->aud ?? null;
        if ($audEsperada && $aud) {
            $auds = is_array($aud) ? $aud : [$aud];
            if (! in_array($audEsperada, $auds, true)) {
                return response()->json(['message' => 'Audiencia del token no válida.'], 401);
            }
        }

        $sub = $payload->sub ?? null;
        if (! $sub) {
            return response()->json(['message' => 'Token sin identificador de usuario (sub).'], 401);
        }

        // Mapea el usuario de Supabase a su perfil local + rol.
        $perfil = Perfil::find($sub);
        if (! $perfil) {
            return response()->json(['message' => 'Usuario sin perfil en el sistema.'], 403);
        }
        if (! $perfil->activo) {
            return response()->json(['message' => 'Usuario desactivado.'], 403);
        }

        // Disponible para controladores y para EnsureRole.
        $request->attributes->set('perfil', $perfil);
        $request->attributes->set('jwt', $payload);
        $request->setUserResolver(fn () => $perfil);

        return $next($request);
    }
}
