<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use App\Support\Alcance;

/**
 * Calidad activa de enlaces WAN/Starlink de un recurso (lectura). Las mediciones
 * (latencia/jitter/pérdida/throughput/MOS) las escribe el job medir_calidad_wan
 * del worker para los recursos opt-in (parametros.wan_calidad).
 */
class WanCalidadController extends Controller
{
    private const RANGOS = ['1h' => '1 hour', '24h' => '24 hours', '7d' => '7 days', '30d' => '30 days'];

    public function index(Request $request, int $id): JsonResponse
    {
        if (! Alcance::permiteRecurso($id)) {
            abort(404);
        }
        $request->validate(['rango' => ['nullable', 'in:1h,24h,7d,30d']]);
        $intervalo = self::RANGOS[$request->query('rango', '24h')];

        $serie = DB::table('wan_calidad')
            ->where('recurso_id', $id)
            ->where('ts', '>=', DB::raw("now() - interval '$intervalo'"))
            ->orderBy('ts')
            ->get();

        $ultimo = DB::table('wan_calidad')
            ->where('recurso_id', $id)
            ->orderByDesc('ts')
            ->first();

        return response()->json([
            'ultimo' => $ultimo,
            'serie'  => $serie,
        ]);
    }
}
