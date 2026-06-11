<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class ReporteController extends Controller
{
    /**
     * Disponibilidad por recurso en un periodo (24h / 7d / 30d).
     *
     * disponibilidad = (up + degraded) / (up + degraded + down) — sobre los
     * chequeos evaluables (excluye 'maintenance' y 'unknown'). Aproximación por
     * conteo de chequeos (intervalo casi uniforme por recurso).
     */
    public function disponibilidad(Request $request): JsonResponse
    {
        $rango = $request->query('rango', '7d');
        $segundos = ['24h' => 86400, '7d' => 604800, '30d' => 2592000][$rango] ?? 604800;
        $desde = now()->subSeconds($segundos);
        $desdeStr = $desde->toDateTimeString();

        $filas = DB::select(
            "SELECT r.id, r.nombre, r.tipo_id, r.sitio_id,
                    t.nombre AS tipo_nombre, s.nombre AS sitio_nombre,
                    r.estado_actual,
                    count(c.id) FILTER (WHERE c.estado <> 'maintenance') AS evaluables_total,
                    count(c.id) FILTER (WHERE c.estado = 'up')          AS up,
                    count(c.id) FILTER (WHERE c.estado = 'degraded')    AS degraded,
                    count(c.id) FILTER (WHERE c.estado = 'down')        AS down,
                    count(c.id) FILTER (WHERE c.estado = 'unknown')     AS unknown,
                    count(c.id) FILTER (WHERE c.estado = 'maintenance') AS mantenimiento,
                    (SELECT count(*) FROM incidencias i
                       WHERE i.recurso_id = r.id AND i.abierta_at >= ?) AS incidencias
             FROM recursos r
             JOIN tipos_recurso t ON t.id = r.tipo_id
             LEFT JOIN sitios s ON s.id = r.sitio_id
             LEFT JOIN chequeos c ON c.recurso_id = r.id AND c.ts >= ?
             GROUP BY r.id, t.nombre, s.nombre
             ORDER BY r.nombre",
            [$desdeStr, $desdeStr]
        );

        $datos = array_map(function ($f) {
            foreach (['evaluables_total', 'up', 'degraded', 'down', 'unknown', 'mantenimiento', 'incidencias'] as $k) {
                $f->$k = (int) $f->$k;
            }
            $base = $f->up + $f->degraded + $f->down;
            $f->disponibilidad = $base > 0 ? round(($f->up + $f->degraded) / $base * 100, 3) : null;

            return $f;
        }, $filas);

        return response()->json([
            'rango'    => $rango,
            'desde'    => $desde->toIso8601String(),
            'recursos' => $datos,
        ]);
    }
}
