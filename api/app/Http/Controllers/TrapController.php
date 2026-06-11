<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/** Lectura de los SNMP traps recibidos (eventos en tiempo real). */
class TrapController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'recurso_id' => ['nullable', 'integer'],
            'severidad'  => ['nullable', 'in:info,warning,critical'],
            'desde'      => ['nullable', 'date'],
        ]);

        $q = DB::table('traps as t')
            ->leftJoin('recursos as r', 'r.id', '=', 't.recurso_id')
            ->select('t.*', 'r.nombre as recurso_nombre');

        if ($request->filled('recurso_id')) {
            $q->where('t.recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('severidad')) {
            $q->where('t.severidad', $request->query('severidad'));
        }
        if ($request->filled('desde')) {
            $q->where('t.ts', '>=', $request->date('desde'));
        }

        $res = $q->orderByDesc('t.ts')->paginate($this->perPage($request, 50));
        $res->getCollection()->transform(function ($r) {
            $r->varbinds = $r->varbinds ? json_decode($r->varbinds) : null;

            return $r;
        });

        return response()->json($res);
    }
}
