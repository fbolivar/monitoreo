<?php

namespace App\Http\Controllers;

use App\Models\Chequeo;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use App\Support\Alcance;

/**
 * Solo lectura. Filtros: recurso_id, estado, desde, hasta (sobre `ts`).
 */
class ChequeoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'recurso_id' => ['nullable', 'integer'],
            'estado'     => ['nullable', 'in:up,degraded,down,unknown,maintenance'],
            'desde'      => ['nullable', 'date'],
            'hasta'      => ['nullable', 'date'],
        ]);

        // Alcance: la telemetria se filtra por los recursos permitidos.
        $q = Alcance::filtrarPorRecurso(Chequeo::query());

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('estado')) {
            $q->where('estado', $request->query('estado'));
        }
        if ($request->filled('desde')) {
            $q->where('ts', '>=', $request->date('desde'));
        }
        if ($request->filled('hasta')) {
            $q->where('ts', '<=', $request->date('hasta'));
        }

        return response()->json($q->orderByDesc('ts')->paginate($this->perPage($request, 50)));
    }

    public function show(int $id): JsonResponse
    {
        $chequeo = Chequeo::with('recurso:id,nombre')->findOrFail($id);
        if (! Alcance::permiteRecurso($chequeo->recurso_id)) {
            abort(404);
        }

        return response()->json($chequeo);
    }
}
