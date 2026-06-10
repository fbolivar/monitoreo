<?php

namespace Tests\Concerns;

use App\Models\Perfil;
use App\Models\Sitio;
use App\Models\TipoRecurso;
use Firebase\JWT\JWT;
use Illuminate\Support\Str;

/**
 * Utilidades para los tests de la API: crea perfiles con rol y firma JWTs
 * de Supabase de prueba (HS256 con SUPABASE_JWT_SECRET de phpunit.xml).
 */
trait CreaUsuariosYTokens
{
    protected function crearPerfil(string $rol, bool $activo = true): Perfil
    {
        return Perfil::create([
            'id'     => (string) Str::uuid(),
            'email'  => $rol.'-'.Str::random(6).'@test.local',
            'nombre' => 'Test '.$rol,
            'rol'    => $rol,
            'activo' => $activo,
        ]);
    }

    /** Genera el header Authorization para un perfil dado. */
    protected function authHeader(Perfil $perfil): array
    {
        $payload = [
            'sub'  => $perfil->id,
            'aud'  => 'authenticated',
            'role' => 'authenticated',
            'email' => $perfil->email,
            'iat'  => time() - 5,
            'exp'  => time() + 3600,
        ];

        $jwt = JWT::encode($payload, config('supabase.jwt_secret'), 'HS256');

        return ['Authorization' => 'Bearer '.$jwt];
    }

    /** Token firmado con un secreto incorrecto (para probar rechazo). */
    protected function authHeaderInvalido(): array
    {
        $jwt = JWT::encode(['sub' => (string) Str::uuid(), 'aud' => 'authenticated', 'exp' => time() + 3600], 'secreto-erroneo', 'HS256');

        return ['Authorization' => 'Bearer '.$jwt];
    }

    /** Asegura un tipo de recurso para crear recursos en los tests. */
    protected function tipoRecurso(): TipoRecurso
    {
        return TipoRecurso::firstOrCreate(
            ['codigo' => 'test_tipo_'.Str::random(4)],
            ['nombre' => 'Tipo de prueba', 'protocolo_default' => 'icmp']
        );
    }

    protected function sitio(): Sitio
    {
        return Sitio::create([
            'codigo' => 'TST-'.Str::random(4),
            'nombre' => 'Sitio de prueba',
        ]);
    }
}
