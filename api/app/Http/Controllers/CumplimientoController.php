<?php

namespace App\Http\Controllers;

use App\Models\PoliticaCumplimiento;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

/** Cumplimiento de configuración (#7): CRUD de políticas + lectura de resultados. */
class CumplimientoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        return response()->json(
            PoliticaCumplimiento::query()->orderBy('nombre')->paginate($this->perPage($request))
        );
    }

    public function show(int $id): JsonResponse
    {
        return response()->json(PoliticaCumplimiento::findOrFail($id));
    }

    public function store(Request $request): JsonResponse
    {
        return response()->json(PoliticaCumplimiento::create($request->validate($this->rules())), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $p = PoliticaCumplimiento::findOrFail($id);
        $p->update($request->validate($this->rules(true)));

        return response()->json($p);
    }

    public function destroy(int $id): JsonResponse
    {
        PoliticaCumplimiento::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    /** Resultados actuales (incumplimientos primero). GET /cumplimiento/resultados */
    public function resultados(Request $request): JsonResponse
    {
        $q = DB::table('cumplimiento_resultados as cr')
            ->join('cumplimiento_politicas as p', 'p.id', '=', 'cr.politica_id')
            ->join('recursos as r', 'r.id', '=', 'cr.recurso_id')
            ->select('cr.*', 'p.nombre as politica', 'p.severidad', 'r.nombre as recurso_nombre')
            ->orderBy('cr.cumple')->orderByDesc('cr.ts');

        if ($request->filled('recurso_id')) {
            $q->where('cr.recurso_id', $request->integer('recurso_id'));
        }

        return response()->json($q->paginate($this->perPage($request, 100)));
    }

    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'nombre'         => [$req, 'string', 'max:255'],
            'descripcion'    => ['nullable', 'string'],
            'tipo'           => [$req, Rule::in(['contiene', 'no_contiene', 'regex'])],
            'patron'         => [$req, 'string'],
            'severidad'      => ['nullable', Rule::in(['info', 'warning', 'critical'])],
            'aplica_tipo_id' => ['nullable', 'integer'],
            'activo'         => ['boolean'],
        ];
    }
}
