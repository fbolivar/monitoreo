<?php

namespace App\Http\Controllers;

use App\Models\Perfil;
use Firebase\JWT\JWT;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;

/**
 * Autenticación LOCAL: verifica email + contraseña (bcrypt en `perfiles`) y
 * emite un JWT propio (HS256) firmado con AUTH_JWT_SECRET. Sin Supabase.
 */
class AuthController extends Controller
{
    public function login(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email'    => ['required', 'email'],
            'password' => ['required', 'string'],
        ]);

        $perfil = Perfil::where('email', $data['email'])->first();

        if (! $perfil
            || ! $perfil->activo
            || ! $perfil->password_hash
            || ! Hash::check($data['password'], $perfil->password_hash)) {
            return response()->json(['message' => 'Credenciales inválidas.'], 401);
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

        return response()->json([
            'token'  => $token,
            'perfil' => $perfil,
        ]);
    }
}
