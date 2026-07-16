<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use App\Support\Alcance;

/** AIOps (#14): grupos de incidencias correlacionadas (lectura). */
class CorrelacionController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        // Alcance: la correlacion vive en un sitio -> se filtra por el propio sitio.
        // (Antes solo se filtraban las incidencias adjuntas y el listado se filtraba
        //  igual, dejando ver grupos de otras territoriales.)
        $corr = DB::table('correlaciones as c')
            ->tap(fn ($q) => Alcance::filtrarPorSitio($q, 'c.sitio_id'))
            ->leftJoin('sitios as s', 's.id', '=', 'c.sitio_id')
            ->select('c.*', 's.nombre as sitio_nombre')
            ->orderByDesc('c.creada_at')
            ->paginate($this->perPage($request, 30));

        // Adjunta las incidencias de cada correlación de la página.
        $ids = collect($corr->items())->pluck('id');
        $incs = DB::table('incidencias as i')
            ->leftJoin('recursos as r', 'r.id', '=', 'i.recurso_id')
            ->tap(fn ($q) => Alcance::filtrarPorRecurso($q, 'i.recurso_id'))
            ->whereIn('i.correlacion_id', $ids)
            ->select('i.id', 'i.correlacion_id', 'i.titulo', 'i.severidad', 'i.estado',
                'i.abierta_at as inicio', 'r.nombre as recurso_nombre')
            ->get()->groupBy('correlacion_id');

        $corr->getCollection()->transform(function ($c) use ($incs) {
            $c->incidencias = $incs->get($c->id, collect())->values();

            return $c;
        });

        return response()->json($corr);
    }
}
