<?php

namespace App\Http\Controllers;

use App\Models\Metrica;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use App\Support\Alcance;

/**
 * Solo lectura (serie temporal). Filtros: recurso_id, metrica, desde, hasta.
 * No expone show por id (PK compuesta); se consulta por filtros.
 */
class MetricaController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'recurso_id' => ['nullable', 'integer'],
            'metrica'    => ['nullable', 'string', 'max:100'],
            'desde'      => ['nullable', 'date'],
            'hasta'      => ['nullable', 'date'],
        ]);

        // Alcance: las metricas se filtran por los recursos permitidos.
        $q = Alcance::filtrarPorRecurso(Metrica::query());

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('metrica')) {
            $q->where('metrica', $request->query('metrica'));
        }
        if ($request->filled('desde')) {
            $q->where('ts', '>=', $request->date('desde'));
        }
        if ($request->filled('hasta')) {
            $q->where('ts', '<=', $request->date('hasta'));
        }

        return response()->json(
            $q->orderByDesc('ts')->paginate($this->perPage($request, 100))
        );
    }
}
