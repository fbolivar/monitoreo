<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * Lectura de la bitácora de auditoría. Solo admin (datos sensibles).
 * Filtros: accion, entidad, buscar (email/descripción), desde, hasta.
 */
class AuditoriaController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'accion'  => ['nullable', 'string'],
            'entidad' => ['nullable', 'string'],
            'buscar'  => ['nullable', 'string'],
            'desde'   => ['nullable', 'date'],
            'hasta'   => ['nullable', 'date'],
        ]);

        $q = DB::table('auditoria');

        if ($request->filled('accion')) {
            $q->where('accion', $request->query('accion'));
        }
        if ($request->filled('entidad')) {
            $q->where('entidad', $request->query('entidad'));
        }
        if ($request->filled('buscar')) {
            $t = '%'.$request->query('buscar').'%';
            $q->where(fn ($w) => $w->where('actor_email', 'ilike', $t)
                                   ->orWhere('descripcion', 'ilike', $t));
        }
        if ($request->filled('desde')) {
            $q->where('ts', '>=', $request->date('desde'));
        }
        if ($request->filled('hasta')) {
            $q->where('ts', '<=', $request->date('hasta'));
        }

        $res = $q->orderByDesc('ts')->paginate($this->perPage($request, 50));

        // jsonb llega como cadena desde el query builder: decodificar para el cliente.
        $res->getCollection()->transform(function ($r) {
            $r->cambios = $r->cambios ? json_decode($r->cambios) : null;

            return $r;
        });

        return response()->json($res);
    }
}
