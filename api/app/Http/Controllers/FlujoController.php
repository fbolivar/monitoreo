<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use App\Support\Alcance;

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
            ->when($recursoId, fn ($q) => $q->where('recurso_id', $recursoId))
            ->tap(fn ($q) => Alcance::filtrarPorRecurso($q, 'recurso_id'));

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

    /**
     * Panel "Overview" estilo NetFlow: KPIs con deltas + sparklines, serie
     * temporal apilada por app, donas (apps/protocolos), top talkers/destinos
     * y top conversaciones (flujo). Todo de la tabla `flujos`.
     */
    public function overview(Request $request): JsonResponse
    {
        $request->validate(['rango' => ['nullable', 'in:1h,6h,24h,7d']]);
        $rango = $request->query('rango', '24h');
        [$intervalo, $bucket, $segs] = [
            '1h'  => ['1 hour', 300, 3600],
            '6h'  => ['6 hours', 900, 21600],
            '24h' => ['24 hours', 3600, 86400],
            '7d'  => ['7 days', 86400, 604800],
        ][$rango];

        $desde = "now() - interval '$intervalo'";
        // Alcance: acota TODAS las consultas del tablero a los recursos permitidos.
        // Los ids se castean a int, por eso es seguro interpolarlos aqui.
        $ids = Alcance::idsParaSql();
        $fAlc = $ids === null ? '' : ' AND recurso_id IN ('.implode(',', array_map('intval', $ids)).')';
        $w = "ventana_fin >= $desde".$fAlc;
        $wPrev = "ventana_fin >= now() - (interval '$intervalo') * 2 AND ventana_fin < $desde".$fAlc;

        // Totales REALES desde flujo_totales (todo el tráfico). Fallback a flujos
        // (top-N) mientras flujo_totales acumula histórico.
        $hayTot = DB::selectOne("SELECT count(*) c FROM flujo_totales WHERE $w")->c > 0;
        $T = $hayTot ? 'flujo_totales' : 'flujos';
        $flowExpr = $hayTot ? 'coalesce(sum(flujos),0)' : 'count(*)';

        // ── KPIs (periodo actual vs anterior) ────────────────────────────
        $cur = DB::selectOne("SELECT coalesce(sum(bytes),0) tb, $flowExpr fl FROM $T WHERE $w");
        $prev = DB::selectOne("SELECT coalesce(sum(bytes),0) tb, $flowExpr fl FROM $T WHERE $wPrev");
        $hosts = DB::selectOne("SELECT count(*) h FROM (SELECT src_ip ip FROM flujos WHERE $w AND src_ip IS NOT NULL UNION SELECT dst_ip FROM flujos WHERE $w AND dst_ip IS NOT NULL) q")->h;
        $hostsPrev = DB::selectOne("SELECT count(*) h FROM (SELECT src_ip ip FROM flujos WHERE $wPrev AND src_ip IS NOT NULL UNION SELECT dst_ip FROM flujos WHERE $wPrev AND dst_ip IS NOT NULL) q")->h;

        $delta = fn ($a, $b) => $b > 0 ? round((($a - $b) / $b) * 100, 1) : null;
        $mbps = fn ($bytes) => round(($bytes * 8) / $segs / 1e6, 1);

        $kpis = [
            'total_bytes' => (int) $cur->tb, 'total_delta' => $delta($cur->tb, $prev->tb),
            'avg_mbps' => $mbps($cur->tb), 'avg_delta' => $delta($cur->tb, $prev->tb),
            'flows' => (int) $cur->fl, 'flows_delta' => $delta($cur->fl, $prev->fl),
            'hosts' => (int) $hosts, 'hosts_delta' => $delta($hosts, $hostsPrev),
        ];

        // ── Serie temporal por bucket ────────────────────────────────────
        // Tráfico/flujos del total real ($T); hosts distintos solo de flujos (top-N).
        $porBucket = DB::select(
            "SELECT floor(extract(epoch from ventana_fin)/$bucket)*$bucket AS tb, sum(bytes) b, $flowExpr c
             FROM $T WHERE $w GROUP BY tb ORDER BY tb"
        );
        $mapB = [];
        foreach ($porBucket as $r) {
            $mapB[(int) $r->tb] = $r;
        }
        $porBucketH = DB::select(
            "SELECT floor(extract(epoch from ventana_fin)/$bucket)*$bucket AS tb, count(distinct src_ip) h
             FROM flujos WHERE $w GROUP BY tb"
        );
        $mapH = [];
        foreach ($porBucketH as $r) {
            $mapH[(int) $r->tb] = (int) $r->h;
        }

        // Eje de buckets completo (rellena vacíos con 0).
        $now = time();
        $b0 = (int) (floor(($now - $segs) / $bucket) * $bucket);
        $bn = (int) (floor($now / $bucket) * $bucket);
        $labels = $traffic = $flows = $hostsSpark = $bucketKeys = [];
        for ($t = $b0; $t <= $bn; $t += $bucket) {
            $bucketKeys[] = $t;
            $labels[] = date($bucket >= 86400 ? 'M d' : 'H:i', $t);
            $traffic[] = (int) ($mapB[$t]->b ?? 0);
            $flows[] = (int) ($mapB[$t]->c ?? 0);
            $hostsSpark[] = $mapH[$t] ?? 0;
        }

        // ── Serie apilada por app (top 5 + otros) ────────────────────────
        $topApps = DB::select("SELECT app, sum(bytes) b FROM $T WHERE $w GROUP BY app ORDER BY b DESC LIMIT 6");
        $appNames = array_map(fn ($r) => $r->app ?: 'otros', $topApps);
        $porBucketApp = DB::select(
            "SELECT floor(extract(epoch from ventana_fin)/$bucket)*$bucket AS tb, app, sum(bytes) b
             FROM $T WHERE $w GROUP BY tb, app"
        );
        $mapBA = [];
        foreach ($porBucketApp as $r) {
            $mapBA[(int) $r->tb][$r->app ?: 'otros'] = (int) $r->b;
        }
        $apilada = [];
        foreach ($appNames as $a) {
            $serie = [];
            foreach ($bucketKeys as $t) {
                $serie[] = $mapBA[$t][$a] ?? 0;
            }
            $apilada[] = ['app' => $a, 'valores' => $serie];
        }

        // ── Donas ────────────────────────────────────────────────────────
        $appsDona = DB::select("SELECT coalesce(app,'otros') app, sum(bytes) bytes FROM $T WHERE $w GROUP BY app ORDER BY bytes DESC LIMIT 6");
        $protoRaw = DB::select("SELECT protocolo, sum(bytes) bytes FROM $T WHERE $w GROUP BY protocolo");
        $protoMap = ['TCP' => 0, 'UDP' => 0, 'ICMP' => 0, 'Otros' => 0];
        foreach ($protoRaw as $r) {
            $k = [6 => 'TCP', 17 => 'UDP', 1 => 'ICMP'][$r->protocolo] ?? 'Otros';
            $protoMap[$k] += (int) $r->bytes;
        }
        $protocolos = [];
        foreach ($protoMap as $k => $v) {
            if ($v > 0) {
                $protocolos[] = ['proto' => $k, 'bytes' => $v];
            }
        }

        // ── Tablas + flujo ───────────────────────────────────────────────
        $total = max(1, (int) $cur->tb);
        $talkers = DB::select("SELECT host(src_ip) ip, sum(bytes) bytes FROM flujos WHERE $w AND src_ip IS NOT NULL GROUP BY src_ip ORDER BY bytes DESC LIMIT 6");
        $destinos = DB::select("SELECT host(dst_ip) ip, sum(bytes) bytes FROM flujos WHERE $w AND dst_ip IS NOT NULL GROUP BY dst_ip ORDER BY bytes DESC LIMIT 6");
        $flujo = DB::select("SELECT host(src_ip) src, host(dst_ip) dst, coalesce(app,'otros') app, sum(bytes) bytes FROM flujos WHERE $w AND src_ip IS NOT NULL AND dst_ip IS NOT NULL GROUP BY src_ip, dst_ip, app ORDER BY bytes DESC LIMIT 8");
        $pct = fn ($b) => round(($b / $total) * 100, 1);

        return response()->json([
            'rango'       => $rango,
            'kpis'        => $kpis,
            'spark'       => ['traffic' => $traffic, 'flows' => $flows, 'hosts' => $hostsSpark, 'bandwidth' => $traffic],
            'serie'       => ['labels' => $labels, 'apilada' => $apilada],
            'apps'        => array_map(fn ($r) => ['app' => $r->app, 'bytes' => (int) $r->bytes], $appsDona),
            'protocolos'  => $protocolos,
            'talkers'     => array_map(fn ($r) => ['ip' => $r->ip, 'bytes' => (int) $r->bytes, 'pct' => $pct($r->bytes)], $talkers),
            'destinos'    => array_map(fn ($r) => ['ip' => $r->ip, 'bytes' => (int) $r->bytes, 'pct' => $pct($r->bytes)], $destinos),
            'flujo'       => array_map(fn ($r) => ['src' => $r->src, 'dst' => $r->dst, 'app' => $r->app, 'bytes' => (int) $r->bytes], $flujo),
        ]);
    }
}
