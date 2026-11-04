<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * Dashboards personalizables del USUARIO ACTUAL. Cada quien ve y edita solo los
 * suyos (no hay dashboards de otros). El layout (widgets) viaja como jsonb.
 */
class DashboardController extends Controller
{
    private function yo(Request $request): string
    {
        return $request->attributes->get('perfil')->id;
    }

    public function index(Request $request): JsonResponse
    {
        $rows = DB::table('dashboards')->where('perfil_id', $this->yo($request))
            ->orderByDesc('es_default')->orderBy('nombre')
            ->get(['id', 'nombre', 'es_default', 'widgets', 'updated_at']);
        $rows->transform(function ($d) {
            $d->widgets = json_decode($d->widgets ?? '[]');
            return $d;
        });

        return response()->json(['data' => $rows]);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->validar($request);
        $id = DB::table('dashboards')->insertGetId([
            'perfil_id'  => $this->yo($request),
            'nombre'     => $data['nombre'],
            'es_default' => $data['es_default'] ?? false,
            'widgets'    => json_encode($data['widgets'] ?? []),
            'created_at' => now(), 'updated_at' => now(),
        ]);
        if (($data['es_default'] ?? false)) {
            $this->unsetOtrosDefault($request, $id);
        }

        return response()->json(['id' => $id], 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $this->propio($request, $id);
        $data = $this->validar($request);
        DB::table('dashboards')->where('id', $id)->update([
            'nombre'     => $data['nombre'],
            'es_default' => $data['es_default'] ?? false,
            'widgets'    => json_encode($data['widgets'] ?? []),
            'updated_at' => now(),
        ]);
        if (($data['es_default'] ?? false)) {
            $this->unsetOtrosDefault($request, $id);
        }

        return response()->json(['id' => $id]);
    }

    public function destroy(Request $request, int $id): JsonResponse
    {
        $this->propio($request, $id);
        DB::table('dashboards')->where('id', $id)->delete();

        return response()->json(null, 204);
    }

    private function validar(Request $request): array
    {
        return $request->validate([
            'nombre'        => ['required', 'string', 'max:120'],
            'es_default'    => ['boolean'],
            'widgets'       => ['present', 'array', 'max:50'],
            'widgets.*.tipo' => ['required', 'string', 'max:40'],
        ]);
    }

    /** 404 si el dashboard no existe o no es del usuario (no se revela cuál). */
    private function propio(Request $request, int $id): void
    {
        $existe = DB::table('dashboards')->where('id', $id)
            ->where('perfil_id', $this->yo($request))->exists();
        if (! $existe) {
            abort(404);
        }
    }

    private function unsetOtrosDefault(Request $request, int $id): void
    {
        DB::table('dashboards')->where('perfil_id', $this->yo($request))
            ->where('id', '<>', $id)->update(['es_default' => false]);
    }
}
