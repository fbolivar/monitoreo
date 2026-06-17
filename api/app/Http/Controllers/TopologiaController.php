<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;

/**
 * Topología L2 (LLDP): grafo de nodos y enlaces.
 *
 * El grafo SIEMPRE incluye TODOS los recursos activos (agrupados por sitio),
 * tengan o no vecinos LLDP, para que el inventario sea visible. Encima se
 * superponen los enlaces descubiertos por LLDP (tabla lldp_vecinos que llena
 * el worker) y los vecinos que NO son recursos gestionados (marcados externos).
 * Lectura para cualquier rol.
 */
class TopologiaController extends Controller
{
    public function index(): JsonResponse
    {
        $nodos = [];   // id => nodo
        $enlaces = [];
        $vistos = [];  // dedup de enlaces no dirigidos

        $addNodo = function (string $id, array $datos) use (&$nodos) {
            if (! isset($nodos[$id])) {
                $nodos[$id] = $datos + ['grado' => 0];
            }
        };

        // 1) Todos los recursos activos como nodos (haya o no LLDP).
        $recursos = DB::table('recursos as r')
            ->leftJoin('sitios as s', 's.id', '=', 'r.sitio_id')
            ->leftJoin('tipos_recurso as t', 't.id', '=', 'r.tipo_id')
            ->where('r.activo', true)
            ->select(
                'r.id', 'r.nombre', 'r.estado_actual',
                'r.sitio_id', 's.nombre as sitio_nombre',
                't.codigo as tipo_codigo', 't.nombre as tipo_nombre'
            )
            ->get();

        foreach ($recursos as $r) {
            $addNodo('r:'.$r->id, [
                'id' => 'r:'.$r->id,
                'nombre' => $r->nombre,
                'estado' => $r->estado_actual,
                'es_recurso' => true,
                'sitio_id' => $r->sitio_id,
                'sitio' => $r->sitio_nombre,
                'tipo' => $r->tipo_codigo,
                'tipo_nombre' => $r->tipo_nombre,
            ]);
        }

        // 2) Enlaces LLDP + vecinos externos.
        $filas = DB::table('lldp_vecinos as v')
            ->join('recursos as r', 'r.id', '=', 'v.recurso_id')
            ->leftJoin('recursos as rr', 'rr.id', '=', 'v.recurso_remoto_id')
            ->where('r.activo', true)
            ->select(
                'v.recurso_id', 'r.nombre as local_nombre', 'r.estado_actual as local_estado',
                'v.local_port', 'v.remote_sysname', 'v.remote_port', 'v.remote_chassis',
                'v.recurso_remoto_id', 'rr.nombre as remoto_nombre',
                'rr.estado_actual as remoto_estado'
            )
            ->get();

        foreach ($filas as $f) {
            $origen = 'r:'.$f->recurso_id;
            // El recurso local ya debería existir (paso 1); por si está inactivo, lo añade.
            $addNodo($origen, [
                'id' => $origen, 'nombre' => $f->local_nombre, 'estado' => $f->local_estado,
                'es_recurso' => true, 'sitio_id' => null, 'sitio' => null, 'tipo' => null, 'tipo_nombre' => null,
            ]);

            if ($f->recurso_remoto_id) {
                $destino = 'r:'.$f->recurso_remoto_id;
                $addNodo($destino, [
                    'id' => $destino, 'nombre' => $f->remoto_nombre, 'estado' => $f->remoto_estado,
                    'es_recurso' => true, 'sitio_id' => null, 'sitio' => null, 'tipo' => null, 'tipo_nombre' => null,
                ]);
            } else {
                // Vecino que no es un recurso gestionado (AP, host, equipo externo).
                $clave = $f->remote_sysname ?: $f->remote_chassis ?: 'ext';
                $destino = 'x:'.$clave;
                $addNodo($destino, [
                    'id' => $destino, 'nombre' => $f->remote_sysname ?: $f->remote_chassis ?: '(desconocido)',
                    'estado' => null, 'es_recurso' => false,
                    'sitio_id' => null, 'sitio' => null, 'tipo' => null, 'tipo_nombre' => null,
                ]);
            }

            // Dedup del enlace por par de extremos (sin dirección).
            $par = [$origen.'|'.($f->local_port ?? ''), $destino.'|'.($f->remote_port ?? '')];
            sort($par);
            $k = implode('::', $par);
            if (isset($vistos[$k])) {
                continue;
            }
            $vistos[$k] = true;

            $nodos[$origen]['grado']++;
            $nodos[$destino]['grado']++;

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
