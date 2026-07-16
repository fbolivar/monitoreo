<?php

namespace App\Http\Controllers;

use App\Models\TipoRecurso;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

class TipoRecursoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        return response()->json(
            TipoRecurso::orderBy('nombre')->paginate($this->perPage($request))
        );
    }

    public function show(int $id): JsonResponse
    {
        return response()->json(TipoRecurso::findOrFail($id));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'codigo'            => ['required', 'string', 'max:50', 'unique:tipos_recurso,codigo'],
            'nombre'            => ['required', 'string', 'max:255'],
            'descripcion'       => ['nullable', 'string'],
            'protocolo_default' => ['required', Rule::in(['icmp', 'snmp', 'http', 'https', 'tcp', 'starlink'])],
            'sla_objetivo'      => ['nullable', 'numeric', 'between:0,100'],
            'icono'             => ['nullable', 'string', 'max:50'],
        ]);

        return response()->json(TipoRecurso::create($data), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $tipo = TipoRecurso::findOrFail($id);

        $data = $request->validate([
            'codigo'            => ['sometimes', 'string', 'max:50', Rule::unique('tipos_recurso', 'codigo')->ignore($tipo->id)],
            'nombre'            => ['sometimes', 'string', 'max:255'],
            'descripcion'       => ['nullable', 'string'],
            'protocolo_default' => ['sometimes', Rule::in(['icmp', 'snmp', 'http', 'https', 'tcp', 'starlink'])],
            'sla_objetivo'      => ['nullable', 'numeric', 'between:0,100'],
            'icono'             => ['nullable', 'string', 'max:50'],
        ]);

        $tipo->update($data);

        return response()->json($tipo);
    }

    public function destroy(int $id): JsonResponse
    {
        TipoRecurso::findOrFail($id)->delete();

        return response()->json(null, 204);
    }
}
