<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;

/**
 * Topología L2 (LLDP): grafo de nodos (switches + vecinos) y enlaces, agregado
 * de la tabla lldp_vecinos que llena el worker. Lectura para cualquier rol.
 */
class TopologiaController extends Controller
{
    public function index(): JsonResponse
    {
        $filas = DB::table('lldp_vecinos as v')
            ->join('recursos as r', 'r.id', '=', 'v.recurso_id')
            ->leftJoin('recursos as rr', 'rr.id', '=', 'v.recurso_remoto_id')
            ->select(
                'v.recurso_id', 'r.nombre as local_nombre', 'r.estado_actual as local_estado',
                'v.local_port', 'v.remote_sysname', 'v.remote_port', 'v.remote_chassis',
                'v.recurso_remoto_id', 'rr.nombre as remoto_nombre',
                'rr.estado_actual as remoto_estado', 'rr.tipo_id as remoto_tipo'
            )
            ->get();

        $nodos = [];
        $enlaces = [];
        $vistos = [];   // dedup de enlaces no dirigidos

        $addNodo = function (string $id, ?string $nombre, ?string $estado, bool $esRecurso) use (&$nodos) {
            if (! isset($nodos[$id])) {
                $nodos[$id] = [
                    'id' => $id,
                    'nombre' => $nombre ?: '(desconocido)',
                    'estado' => $estado,
                    'es_recurso' => $esRecurso,
                ];
            }
        };

        foreach ($filas as $f) {
            $origen = 'r:'.$f->recurso_id;
            $addNodo($origen, $f->local_nombre, $f->local_estado, true);

            if ($f->recurso_remoto_id) {
                $destino = 'r:'.$f->recurso_remoto_id;
                $addNodo($destino, $f->remoto_nombre, $f->remoto_estado, true);
            } else {
                // Vecino que no es un recurso gestionado (AP, servidor, equipo externo).
                $clave = $f->remote_sysname ?: $f->remote_chassis ?: 'ext';
                $destino = 'x:'.$clave;
                $addNodo($destino, $f->remote_sysname ?: $f->remote_chassis, null, false);
            }

            // Dedup del enlace por par de extremos (sin dirección).
            $par = [$origen.'|'.($f->local_port ?? ''), $destino.'|'.($f->remote_port ?? '')];
            sort($par);
            $k = implode('::', $par);
            if (isset($vistos[$k])) {
                continue;
            }
            $vistos[$k] = true;

            $enlaces[] = [
                'origen' => $origen,
                'origen_port' => $f->local_port,
                'destino' => $destino,
                'destino_port' => $f->remote_port,
            ];
        }

        return response()->json([
            'nodos' => array_values($nodos),
            'enlaces' => $enlaces,
        ]);
    }
}
