<?php

namespace App\Http\Controllers;

use App\Models\Auditoria;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * Relevo de turno del NOC (handover): el operador saliente deja por escrito el
 * estado (pendientes, en curso, ojo con X) para el entrante. Lectura para cualquier
 * rol autenticado; registrar un relevo es de admin/operador.
 */
class RelevoController extends Controller
{
    /** Últimos relevos (el más reciente primero). */
    public function index(Request $request): JsonResponse
    {
        $limite = min(50, max(1, (int) $request->query('limite', 20)));
        $relevos = DB::table('relevos_turno')
            ->orderByDesc('creado_at')
            ->limit($limite)
            ->get(['id', 'actor_email', 'resumen', 'creado_at']);

        return response()->json(['data' => $relevos]);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate(['resumen' => ['required', 'string', 'min:1', 'max:8000']]);
        $perfil = $request->attributes->get('perfil');

        $id = DB::table('relevos_turno')->insertGetId([
            'perfil_id'   => optional($perfil)->id,
            'actor_email' => optional($perfil)->email ?? 'desconocido',
            'resumen'     => trim($data['resumen']),
            'creado_at'   => now(),
        ]);
        Auditoria::registrar('crear', 'relevo_turno', $id, 'Relevo de turno NOC');

        return response()->json(
            DB::table('relevos_turno')->where('id', $id)->first(['id', 'actor_email', 'resumen', 'creado_at']),
            201
        );
    }
}
