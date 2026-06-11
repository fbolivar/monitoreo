<?php

namespace App\Support;

use Illuminate\Support\Facades\DB;

/**
 * Registro de la bitácora de auditoría. Lo invocan el AuditObserver (CRUD de
 * entidades) y algunos controladores (login). El actor sale del request salvo
 * que se pase explícito (p. ej. en el login, donde aún no hay usuario resuelto).
 */
class Auditoria
{
    public static function registrar(
        string $accion,
        string $entidad,
        $entidadId = null,
        ?string $descripcion = null,
        ?array $cambios = null,
        $actor = null,
    ): void {
        $request = request();
        $actor = $actor ?? ($request ? $request->user() : null);

        $ipRaw = $request ? ($request->header('X-Forwarded-For') ?: $request->ip()) : null;
        if ($ipRaw) {
            $ipRaw = trim(explode(',', $ipRaw)[0]);
        }
        $ip = ($ipRaw && filter_var($ipRaw, FILTER_VALIDATE_IP)) ? $ipRaw : null;

        DB::table('auditoria')->insert([
            'perfil_id'   => $actor?->id,
            'actor_email' => $actor?->email,
            'actor_rol'   => $actor?->rol,
            'accion'      => $accion,
            'entidad'     => $entidad,
            'entidad_id'  => $entidadId !== null ? (string) $entidadId : null,
            'descripcion' => $descripcion,
            'cambios'     => $cambios ? json_encode($cambios, JSON_UNESCAPED_UNICODE) : null,
            'ip'          => $ip,
        ]);
    }
}
