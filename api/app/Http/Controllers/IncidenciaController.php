<?php

namespace App\Http\Controllers;

use App\Models\Incidencia;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/**
 * Solo lectura en esta fase. Filtros: recurso_id, estado, severidad,
 * desde, hasta (sobre `abierta_at`).
 */
class IncidenciaController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'recurso_id' => ['nullable', 'integer'],
            'estado'     => ['nullable', 'in:abierta,reconocida,resuelta'],
            'severidad'  => ['nullable', 'in:info,warning,critical'],
            'desde'      => ['nullable', 'date'],
            'hasta'      => ['nullable', 'date'],
        ]);

        $q = Incidencia::query()->with(['recurso:id,nombre', 'reconocidaPor:id,nombre,email']);

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('estado')) {
            $q->where('estado', $request->query('estado'));
        }
        if ($request->filled('severidad')) {
            $q->where('severidad', $request->query('severidad'));
        }
        if ($request->filled('desde')) {
            $q->where('abierta_at', '>=', $request->date('desde'));
        }
        if ($request->filled('hasta')) {
            $q->where('abierta_at', '<=', $request->date('hasta'));
        }

        return response()->json($q->orderByDesc('abierta_at')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        return response()->json(
            Incidencia::with(['recurso', 'reconocidaPor:id,nombre,email'])->findOrFail($id)
        );
    }

    /** Reconocer una incidencia (admin/operador). El worker la sigue considerando
     *  abierta (estado <> resuelta), así que no abre una nueva. */
    public function reconocer(Request $request, int $id): JsonResponse
    {
        $inc = Incidencia::findOrFail($id);
        if ($inc->estado === 'resuelta') {
            return response()->json(['message' => 'La incidencia ya está resuelta.'], 422);
        }

        $inc->update([
            'estado'         => 'reconocida',
            'reconocida_at'  => $inc->reconocida_at ?? now(),
            'reconocida_por' => optional($request->attributes->get('perfil'))->id,
        ]);

        return response()->json($inc->load(['recurso:id,nombre', 'reconocidaPor:id,nombre,email']));
    }

    /** Resolver una incidencia manualmente (admin/operador). Si el recurso sigue
     *  caído, el worker abrirá una nueva incidencia en el próximo chequeo. */
    public function resolver(int $id): JsonResponse
    {
        $inc = Incidencia::findOrFail($id);
        if ($inc->estado === 'resuelta') {
            return response()->json(['message' => 'La incidencia ya está resuelta.'], 422);
        }

        $inc->update(['estado' => 'resuelta', 'resuelta_at' => now()]);

        return response()->json($inc->load(['recurso:id,nombre', 'reconocidaPor:id,nombre,email']));
    }
}
