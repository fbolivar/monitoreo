<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use App\Support\Alcance;

/**
 * Solo lectura: pronósticos de capacidad calculados por el worker (regresión
 * sobre el rollup diario). Los más urgentes (menos días) primero.
 */
class PronosticoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $q = DB::table('pronosticos as p')
            ->join('recursos as r', 'r.id', '=', 'p.recurso_id')
            ->tap(fn ($q) => Alcance::filtrarPorRecurso($q, 'p.recurso_id'))
            ->select('p.recurso_id', 'r.nombre as recurso_nombre', 'p.metrica', 'p.ts',
                'p.valor_actual', 'p.pendiente_dia', 'p.dias_restantes', 'p.techo',
                'p.r2', 'p.muestras');

        if ($request->filled('recurso_id')) {
            $q->where('p.recurso_id', $request->integer('recurso_id'));
        }
        // solo=alertables: los que tienen una fecha estimada de agotamiento.
        if ($request->boolean('con_proyeccion')) {
            $q->whereNotNull('p.dias_restantes');
        }

        // Urgentes primero (días ascendente); los sin proyección, al final.
        $rows = $q->orderByRaw('p.dias_restantes ASC NULLS LAST')
            ->orderBy('p.recurso_id')
            ->get();

        return response()->json($rows);
    }
}
