<?php

namespace App\Http\Controllers;

use App\Models\Recurso;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class RecursoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $q = Recurso::query()->with(['tipo:id,codigo,nombre', 'sitio:id,codigo,nombre']);

        if ($request->filled('tipo_id')) {
            $q->where('tipo_id', $request->integer('tipo_id'));
        }
        if ($request->filled('sitio_id')) {
            $q->where('sitio_id', $request->integer('sitio_id'));
        }
        if ($request->filled('estado')) {
            $q->where('estado_actual', $request->query('estado'));
        }
        if ($request->filled('activo')) {
            $q->where('activo', $request->boolean('activo'));
        }
        if ($request->filled('buscar')) {
            $term = '%'.$request->query('buscar').'%';
            $q->where(fn ($w) => $w->where('nombre', 'ilike', $term)->orWhere('hostname', 'ilike', $term));
        }

        return response()->json($q->orderBy('nombre')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        $recurso = Recurso::with(['tipo', 'sitio'])->findOrFail($id);

        // Informa SI hay secretos, sin exponerlos nunca.
        $data = $recurso->toArray();
        $data['tiene_secretos'] = $recurso->tieneSecretos();

        return response()->json($data);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $secretos = $data['secretos'] ?? null;
        unset($data['secretos']);

        $recurso = new Recurso($data);
        if ($request->has('secretos')) {
            $recurso->setSecretosPlanos($secretos);
        }
        $recurso->save();

        return response()->json($recurso->fresh(['tipo', 'sitio']), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $recurso = Recurso::findOrFail($id);
        $data = $request->validate($this->rules(true));

        // Si viene la clave 'secretos' (incluso null), se actualiza el secreto.
        if ($request->has('secretos')) {
            $recurso->setSecretosPlanos($data['secretos'] ?? null);
        }
        unset($data['secretos']);

        $recurso->update($data);

        return response()->json($recurso->fresh(['tipo', 'sitio']));
    }

    public function destroy(int $id): JsonResponse
    {
        Recurso::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'tipo_id'            => [$req, 'integer', 'exists:tipos_recurso,id'],
            'sitio_id'           => ['nullable', 'integer', 'exists:sitios,id'],
            'nombre'             => [$req, 'string', 'max:255'],
            'hostname'           => ['nullable', 'string', 'max:255'],
            'descripcion'        => ['nullable', 'string'],
            'parametros'         => ['nullable', 'array'],
            'intervalo_segundos' => ['nullable', 'integer', 'between:5,86400'],
            'activo'             => ['boolean'],
            // Secretos en claro (jsonb). Se cifran de forma transparente. Nunca se devuelven.
            'secretos'           => ['nullable', 'array'],
        ];
    }
}
