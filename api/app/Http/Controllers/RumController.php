<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/** APM/RUM (#13): lectura de la experiencia real del usuario (agregados). */
class RumController extends Controller
{
    private const RANGOS = ['1h' => '1 hour', '24h' => '24 hours', '7d' => '7 days'];

    public function index(Request $request): JsonResponse
    {
        $request->validate(['rango' => ['nullable', 'in:1h,24h,7d']]);
        $intervalo = self::RANGOS[$request->query('rango', '24h')];
        $desde = DB::raw("now() - interval '$intervalo'");

        $base = fn () => DB::table('rum_eventos')->where('ts', '>=', $desde)->where('tipo', 'pageload');

        $kpis = $base()->selectRaw(
            'count(*) as muestras, avg(valor_ms) as avg_ms, '.
            'percentile_cont(0.95) within group (order by valor_ms) as p95_ms, max(valor_ms) as max_ms'
        )->first();

        $porUrl = $base()->whereNotNull('url')
            ->select('url', DB::raw('count(*) as muestras'), DB::raw('avg(valor_ms) as avg_ms'),
                DB::raw('max(valor_ms) as max_ms'))
            ->groupBy('url')->orderByDesc('muestras')->limit(20)->get();

        $errores = DB::table('rum_eventos')->where('ts', '>=', $desde)->where('tipo', 'error')->count();

        $spans = DB::table('spans')->where('ts', '>=', $desde)
            ->select('servicio', DB::raw('count(*) as n'), DB::raw('avg(dur_ms) as avg_ms'))
            ->groupBy('servicio')->orderByDesc('n')->limit(20)->get();

        return response()->json([
            'rango'   => $request->query('rango', '24h'),
            'kpis'    => $kpis,
            'errores' => $errores,
            'por_url' => $porUrl,
            'spans'   => $spans,
        ]);
    }
}
