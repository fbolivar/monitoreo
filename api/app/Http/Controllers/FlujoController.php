<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * Análisis de flujos de tráfico (NetFlow/IPFIX). Lectura para cualquier rol.
 * Las filas las escribe el colector simon-netflow (top conversaciones por ventana).
 * Devuelve agregados listos para graficar: top hablantes, destinos, apps y
 * conversaciones, en una ventana de tiempo.
 */
class FlujoController extends Controller
{
    private const RANGOS = ['1h' => '1 hour', '6h' => '6 hours', '24h' => '24 hours', '7d' => '7 days'];

    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'recurso_id' => ['nullable', 'integer'],
            'rango'      => ['nullable', 'in:1h,6h,24h,7d'],
            'limite'     => ['nullable', 'integer', 'min:1', 'max:100'],
        ]);

        $intervalo = self::RANGOS[$request->query('rango', '1h')];
        $limite = (int) $request->query('limite', 15);
        $recursoId = $request->filled('recurso_id') ? $request->integer('recurso_id') : null;

        $base = fn () => DB::table('flujos')
            ->where('ventana_fin', '>=', DB::raw("now() - interval '$intervalo'"))
            ->when($recursoId, fn ($q) => $q->where('recurso_id', $recursoId));

        // Top hablantes (origen), destinos y aplicaciones por bytes.
        $talkers = $base()
            ->select('src_ip as ip', DB::raw('sum(bytes) as bytes'), DB::raw('sum(paquetes) as paquetes'))
            ->whereNotNull('src_ip')->groupBy('src_ip')
            ->orderByDesc('bytes')->limit($limite)->get();

        $destinos = $base()
            ->select('dst_ip as ip', DB::raw('sum(bytes) as bytes'), DB::raw('sum(paquetes) as paquetes'))
            ->whereNotNull('dst_ip')->groupBy('dst_ip')
            ->orderByDesc('bytes')->limit($limite)->get();

        $apps = $base()
            ->select('app', DB::raw('sum(bytes) as bytes'), DB::raw('sum(paquetes) as paquetes'))
            ->groupBy('app')->orderByDesc('bytes')->limit($limite)->get();

        $conversaciones = $base()
            ->select('src_ip', 'dst_ip', 'dst_port', 'protocolo', 'app',
                DB::raw('sum(bytes) as bytes'), DB::raw('sum(paquetes) as paquetes'))
            ->groupBy('src_ip', 'dst_ip', 'dst_port', 'protocolo', 'app')
            ->orderByDesc('bytes')->limit($limite)->get();

        $totalBytes = (int) $base()->sum('bytes');

        return response()->json([
            'rango'           => $request->query('rango', '1h'),
            'total_bytes'     => $totalBytes,
            'talkers'         => $talkers,
            'destinos'        => $destinos,
            'apps'            => $apps,
            'conversaciones'  => $conversaciones,
        ]);
    }
}
