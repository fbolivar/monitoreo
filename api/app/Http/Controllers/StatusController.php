<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;

/**
 * Página de estado PÚBLICA (#12): resumen de disponibilidad por sede, sin
 * autenticación y sin datos sensibles (solo nombres y estado agregado).
 */
class StatusController extends Controller
{
    public function index(): JsonResponse
    {
        $recursos = DB::table('recursos as r')
            ->leftJoin('sitios as s', 's.id', '=', 'r.sitio_id')
            ->where('r.activo', true)
            ->select('r.estado_actual', 's.id as sitio_id', 's.nombre as sitio')
            ->get();

        $sedes = [];
        $globalPeor = 'up';
        $orden = ['up' => 1, 'maintenance' => 2, 'unknown' => 3, 'degraded' => 4, 'down' => 5];

        foreach ($recursos as $r) {
            $sid = $r->sitio_id ?? 0;
            if (! isset($sedes[$sid])) {
                $sedes[$sid] = ['sitio' => $r->sitio ?? 'Sin sede', 'up' => 0, 'degraded' => 0,
                    'down' => 0, 'otros' => 0, 'total' => 0, 'estado' => 'up'];
            }
            $sedes[$sid]['total']++;
            $e = $r->estado_actual;
            if ($e === 'up') {
                $sedes[$sid]['up']++;
            } elseif ($e === 'degraded') {
                $sedes[$sid]['degraded']++;
            } elseif ($e === 'down') {
                $sedes[$sid]['down']++;
            } else {
                $sedes[$sid]['otros']++;
            }
            if (($orden[$e] ?? 0) > ($orden[$sedes[$sid]['estado']] ?? 0)) {
                $sedes[$sid]['estado'] = $e;
            }
            if (($orden[$e] ?? 0) > ($orden[$globalPeor] ?? 0)) {
                $globalPeor = $e;
            }
        }

        $totalDown = array_sum(array_column($sedes, 'down'));
        $totalDeg = array_sum(array_column($sedes, 'degraded'));
        $operativo = $totalDown === 0 && $totalDeg === 0;

        return response()->json([
            'operativo'    => $operativo,
            'estado_global' => $globalPeor,
            'actualizado'  => now()->toIso8601String(),
            'sedes'        => array_values($sedes),
        ]);
    }
}
