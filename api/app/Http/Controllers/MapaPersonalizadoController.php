<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * Mapas personalizados (lienzos con nodos + enlaces). Compartidos: lectura para
 * cualquier rol, gestión admin/operador. El layout viaja como jsonb.
 */
class MapaPersonalizadoController extends Controller
{
    public function index(): JsonResponse
    {
        $rows = DB::table('mapas')->orderBy('nombre')->get(['id', 'nombre', 'updated_at']);

        return response()->json(['data' => $rows]);
    }

    public function show(int $id): JsonResponse
    {
        $m = DB::table('mapas')->find($id);
        if (! $m) {
            abort(404);
        }
        $m->layout = json_decode($m->layout ?? '{}');

        return response()->json($m);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->validar($request);
        $id = DB::table('mapas')->insertGetId($data + ['created_at' => now(), 'updated_at' => now()]);

        return response()->json(['id' => $id], 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        if (! DB::table('mapas')->where('id', $id)->exists()) {
            abort(404);
        }
        DB::table('mapas')->where('id', $id)->update($this->validar($request) + ['updated_at' => now()]);

        return response()->json(['id' => $id]);
    }

    public function destroy(int $id): JsonResponse
    {
        DB::table('mapas')->where('id', $id)->delete();

        return response()->json(null, 204);
    }

    private function validar(Request $request): array
    {
        $v = $request->validate([
            'nombre'           => ['required', 'string', 'max:120'],
            'fondo_url'        => ['nullable', 'string', 'max:2000'],
            'ancho'            => ['required', 'integer', 'between:200,8000'],
            'alto'             => ['required', 'integer', 'between:200,8000'],
            'layout'           => ['present', 'array'],
            'layout.nodos'     => ['present', 'array', 'max:500'],
            'layout.enlaces'   => ['present', 'array', 'max:1000'],
        ]);

        return [
            'nombre'    => $v['nombre'],
            'fondo_url' => $v['fondo_url'] ?? null,
            'ancho'     => $v['ancho'],
            'alto'      => $v['alto'],
            'layout'    => json_encode($v['layout']),
        ];
    }
}
