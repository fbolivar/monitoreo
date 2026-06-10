<?php

namespace App\Http\Controllers;

use App\Models\Mantenimiento;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class MantenimientoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $q = Mantenimiento::query()->with(['recurso:id,nombre', 'sitio:id,nombre']);

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('sitio_id')) {
            $q->where('sitio_id', $request->integer('sitio_id'));
        }
        if ($request->boolean('vigentes')) {
            $q->where('inicio', '<=', now())->where('fin', '>=', now());
        }

        return response()->json($q->orderByDesc('inicio')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        return response()->json(Mantenimiento::with(['recurso', 'sitio'])->findOrFail($id));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $data['creado_por'] = optional($request->attributes->get('perfil'))->id;

        return response()->json(Mantenimiento::create($data), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $mant = Mantenimiento::findOrFail($id);
        $data = $request->validate($this->rules(true));
        $mant->update($data);

        return response()->json($mant);
    }

    public function destroy(int $id): JsonResponse
    {
        Mantenimiento::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'recurso_id' => ['nullable', 'integer', 'exists:recursos,id'],
            'sitio_id'   => ['nullable', 'integer', 'exists:sitios,id'],
            'inicio'     => [$req, 'date'],
            'fin'        => [$req, 'date', 'after:inicio'],
            'motivo'     => [$req, 'string', 'max:500'],
        ];
    }
}
