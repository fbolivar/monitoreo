<?php

namespace App\Http\Controllers;

use App\Models\Recurso;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

class RecursoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $q = Recurso::query()->with([
            'tipo:id,codigo,nombre', 'sitio:id,codigo,nombre', 'dependeDe:id,nombre',
        ]);

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
        $recurso = Recurso::with(['tipo', 'sitio', 'dependeDe:id,nombre'])->findOrFail($id);

        // Informa SI hay secretos, sin exponerlos nunca.
        $data = $recurso->toArray();
        $data['tiene_secretos'] = $recurso->tieneSecretos();

        return response()->json($data);
    }

    /** Snapshot de interfaces de red (IF-MIB) del recurso, si las monitorea. */
    public function interfaces(int $id): JsonResponse
    {
        Recurso::findOrFail($id);

        $rows = DB::table('interfaces')
            ->where('recurso_id', $id)
            ->orderBy('if_index')
            ->get();

        return response()->json($rows);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $this->validarDependencia(null, $data['depende_de_id'] ?? null);
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

        if (array_key_exists('depende_de_id', $data)) {
            $this->validarDependencia($id, $data['depende_de_id']);
        }

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
            'depende_de_id'      => ['nullable', 'integer', 'exists:recursos,id'],
            // Secretos en claro (jsonb). Se cifran de forma transparente. Nunca se devuelven.
            'secretos'           => ['nullable', 'array'],
        ];
    }

    /**
     * Evita autodependencia y ciclos en la cadena depende_de_id.
     * $id es el recurso que se edita (null al crear); $padreId el padre propuesto.
     */
    private function validarDependencia(?int $id, $padreId): void
    {
        if (!$padreId) {
            return;
        }
        $padreId = (int) $padreId;
        if ($id && $padreId === $id) {
            throw ValidationException::withMessages(
                ['depende_de_id' => 'Un recurso no puede depender de sí mismo.']);
        }

        // Sube por la cadena del padre; si reaparece $id (o se repite un nodo) hay ciclo.
        $actual = $padreId;
        $vistos = [];
        while ($actual && !in_array($actual, $vistos, true)) {
            if ($id && $actual === $id) {
                throw ValidationException::withMessages(
                    ['depende_de_id' => 'La dependencia crearía un ciclo.']);
            }
            $vistos[] = $actual;
            $actual = (int) (DB::table('recursos')->where('id', $actual)->value('depende_de_id') ?? 0);
        }
    }
}
