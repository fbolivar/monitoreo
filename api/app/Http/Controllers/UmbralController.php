<?php

namespace App\Http\Controllers;

use App\Models\Umbral;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;
use App\Support\Alcance;

class UmbralController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        // Alcance: umbrales de sus recursos + los globales por tipo (política de la entidad).
        $q = Alcance::filtrarConfigRecurso(Umbral::query());

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('tipo_id')) {
            $q->where('tipo_id', $request->integer('tipo_id'));
        }
        if ($request->filled('metrica')) {
            $q->where('metrica', $request->query('metrica'));
        }

        return response()->json($q->orderBy('id')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        $umbral = Umbral::findOrFail($id);
        Alcance::exigirLecturaConfig($umbral->recurso_id);

        return response()->json($umbral);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $this->validarScopeYValores($data);
        Alcance::exigirEscrituraConfig($data['recurso_id'] ?? null);

        return response()->json(Umbral::create($data), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $umbral = Umbral::findOrFail($id);
        $data = $request->validate($this->rules(true));
        $this->validarScopeYValores(array_merge($umbral->toArray(), $data));

        // Se comprueban AMBOS extremos: la fila actual y a dónde la quiere mover
        // (si no, un acotado convertiría su umbral en uno global, o lo ataría a un
        // recurso ajeno).
        Alcance::exigirEscrituraConfig($umbral->recurso_id);
        if (array_key_exists('recurso_id', $data)) {
            Alcance::exigirEscrituraConfig($data['recurso_id']);
        }

        $umbral->update($data);

        return response()->json($umbral);
    }

    public function destroy(int $id): JsonResponse
    {
        $umbral = Umbral::findOrFail($id);
        Alcance::exigirEscrituraConfig($umbral->recurso_id);
        $umbral->delete();

        return response()->json(null, 204);
    }

    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'recurso_id'        => ['nullable', 'integer', 'exists:recursos,id'],
            'tipo_id'           => ['nullable', 'integer', 'exists:tipos_recurso,id'],
            'metrica'           => [$req, 'string', 'max:100'],
            'operador'          => [$req, Rule::in(['>', '>=', '<', '<=', '==', '!='])],
            'valor_warning'     => ['nullable', 'numeric'],
            'valor_critical'    => ['nullable', 'numeric'],
            'duracion_segundos' => ['nullable', 'integer', 'min:0'],
            'activo'            => ['boolean'],
        ];
    }

    /** Replica las reglas del esquema: scope XOR recurso/tipo y al menos un valor. */
    private function validarScopeYValores(array $d): void
    {
        $tieneRecurso = ! empty($d['recurso_id']);
        $tieneTipo    = ! empty($d['tipo_id']);

        if ($tieneRecurso === $tieneTipo) {
            throw ValidationException::withMessages([
                'recurso_id' => ['Debe indicar exactamente uno: recurso_id o tipo_id.'],
            ]);
        }

        if (($d['valor_warning'] ?? null) === null && ($d['valor_critical'] ?? null) === null) {
            throw ValidationException::withMessages([
                'valor_warning' => ['Debe definir al menos valor_warning o valor_critical.'],
            ]);
        }
    }
}
