<?php

namespace App\Http\Controllers;

use App\Models\Sitio;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

class SitioController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $q = Sitio::query();

        if ($request->filled('activo')) {
            $q->where('activo', $request->boolean('activo'));
        }
        if ($request->filled('ciudad')) {
            $q->where('ciudad', $request->query('ciudad'));
        }

        return response()->json($q->orderBy('nombre')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        return response()->json(Sitio::findOrFail($id));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());

        return response()->json(Sitio::create($data), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $sitio = Sitio::findOrFail($id);
        $data = $request->validate($this->rules($sitio->id, true));
        $sitio->update($data);

        return response()->json($sitio);
    }

    public function destroy(int $id): JsonResponse
    {
        Sitio::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    private function rules(?int $id = null, bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'codigo'      => [$req, 'string', 'max:50', Rule::unique('sitios', 'codigo')->ignore($id)],
            'nombre'      => [$req, 'string', 'max:255'],
            'direccion'   => ['nullable', 'string', 'max:255'],
            'ciudad'      => ['nullable', 'string', 'max:120'],
            'latitud'     => ['nullable', 'numeric', 'between:-90,90'],
            'longitud'    => ['nullable', 'numeric', 'between:-180,180'],
            'descripcion' => ['nullable', 'string'],
            'activo'      => ['boolean'],
        ];
    }
}
