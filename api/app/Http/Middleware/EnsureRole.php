<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Autorización por rol. Se usa DESPUÉS de auth.jwt (JWT propio local).
 * Uso en rutas:  ->middleware('role:admin,operador')
 *
 * Roles del sistema (perfiles.rol):
 *   - admin    : control total, incluida la gestión de usuarios.
 *   - operador : gestiona configuración de monitoreo; NO toca usuarios.
 *   - viewer   : solo lectura (rol "lectura").
 */
class EnsureRole
{
    public function handle(Request $request, Closure $next, string ...$roles): Response
    {
        $perfil = $request->attributes->get('perfil');

        if (! $perfil) {
            return response()->json(['message' => 'No autenticado.'], 401);
        }

        if (! in_array($perfil->rol, $roles, true)) {
            return response()->json([
                'message'        => 'No tiene permisos para esta acción.',
                'rol_actual'     => $perfil->rol,
                'roles_requeridos' => $roles,
            ], 403);
        }

        return $next($request);
    }
}
