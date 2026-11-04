<?php

namespace App\Http\Controllers;

use App\Support\Alcance;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/** Lectura de eventos syslog recibidos (UDP/514, servicio simon-syslog). */
class SyslogController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'recurso_id' => ['nullable', 'integer'],
            'severidad'  => ['nullable', 'in:info,warning,critical'],
            'texto'      => ['nullable', 'string', 'max:200'],
            'desde'      => ['nullable', 'date'],
        ]);

        $q = DB::table('syslog_eventos as s')
            ->leftJoin('recursos as r', 'r.id', '=', 's.recurso_id')
            ->tap(fn ($q) => Alcance::filtrarPorRecurso($q, 's.recurso_id'))
            ->select('s.*', 'r.nombre as recurso_nombre');

        if ($request->filled('recurso_id')) {
            $q->where('s.recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('severidad')) {
            $q->where('s.severidad', $request->query('severidad'));
        }
        if ($request->filled('texto')) {
            $t = '%'.str_replace(['%', '_'], ['\%', '\_'], $request->query('texto')).'%';
            $q->where(fn ($w) => $w->where('s.mensaje', 'ilike', $t)
                ->orWhere('s.hostname', 'ilike', $t)->orWhere('s.app', 'ilike', $t));
        }
        if ($request->filled('desde')) {
            $q->where('s.ts', '>=', $request->date('desde'));
        }

        return response()->json($q->orderByDesc('s.ts')->paginate($this->perPage($request, 100)));
    }
}
