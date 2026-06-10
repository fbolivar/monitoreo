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
}
