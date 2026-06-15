<?php

namespace App\Http\Controllers;

use App\Models\Regla;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

/**
 * Triggers compuestos (multi-condición). La `expresion` es un AST JSON:
 *   hoja:  {"metrica":"cpu","op":">","valor":90}
 *   nodo:  {"and":[...]} | {"or":[...]} | {"not":{...}}
 * El worker lo evalúa con un intérprete puro (monitor/reglas.py).
 */
class ReglaController extends Controller
{
    private const OPERADORES = ['>', '>=', '<', '<=', '==', '!='];

    public function index(Request $request): JsonResponse
    {
        $q = Regla::query();

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('tipo_id')) {
            $q->where('tipo_id', $request->integer('tipo_id'));
        }

        return response()->json($q->orderBy('id')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        return response()->json(Regla::findOrFail($id));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $this->validarScope($data);
        $this->validarExpresion($data['expresion']);

        return response()->json(Regla::create($data), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $regla = Regla::findOrFail($id);
        $data = $request->validate($this->rules(true));
        $this->validarScope(array_merge($regla->toArray(), $data));
        if (array_key_exists('expresion', $data)) {
            $this->validarExpresion($data['expresion']);
        }

        $regla->update($data);

        return response()->json($regla);
    }

    public function destroy(int $id): JsonResponse
    {
        Regla::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'recurso_id'        => ['nullable', 'integer', 'exists:recursos,id'],
            'tipo_id'           => ['nullable', 'integer', 'exists:tipos_recurso,id'],
            'nombre'            => [$req, 'string', 'max:150'],
            'descripcion'       => ['nullable', 'string', 'max:500'],
            'expresion'         => [$req, 'array'],
            'severidad'         => ['nullable', Rule::in(['info', 'warning', 'critical'])],
            'duracion_segundos' => ['nullable', 'integer', 'min:0'],
            'activo'            => ['boolean'],
        ];
    }

    /** Igual que el esquema: exactamente uno de recurso_id / tipo_id. */
    private function validarScope(array $d): void
    {
        $tieneRecurso = ! empty($d['recurso_id']);
        $tieneTipo    = ! empty($d['tipo_id']);

        if ($tieneRecurso === $tieneTipo) {
            throw ValidationException::withMessages([
                'recurso_id' => ['Debe indicar exactamente uno: recurso_id o tipo_id.'],
            ]);
        }
    }

    /** Valida la forma del AST (defensa en profundidad; el worker revalida). */
    private function validarExpresion($expr, int $profundidad = 0): void
    {
        $err = $this->revisarNodo($expr, $profundidad);
        if ($err !== null) {
            throw ValidationException::withMessages(['expresion' => [$err]]);
        }
    }

    private function revisarNodo($expr, int $profundidad): ?string
    {
        if ($profundidad > 20) {
            return 'La expresión está demasiado anidada.';
        }
        if (! is_array($expr)) {
            return 'Cada nodo de la expresión debe ser un objeto.';
        }

        $claves = array_intersect(['and', 'or', 'not', 'metrica'], array_keys($expr));
        if (count($claves) !== 1) {
            return 'Cada nodo debe tener exactamente uno de: and, or, not, metrica.';
        }

        if (isset($expr['and']) || isset($expr['or'])) {
            $hijos = $expr['and'] ?? $expr['or'];
            if (! is_array($hijos) || count($hijos) === 0 || array_keys($hijos) !== range(0, count($hijos) - 1)) {
                return 'and/or requieren una lista no vacía de subexpresiones.';
            }
            foreach ($hijos as $h) {
                if ($e = $this->revisarNodo($h, $profundidad + 1)) {
                    return $e;
                }
            }

            return null;
        }

        if (isset($expr['not'])) {
            return $this->revisarNodo($expr['not'], $profundidad + 1);
        }

        // Hoja {metrica, op, valor}
        if (! is_string($expr['metrica']) || $expr['metrica'] === '') {
            return 'Cada hoja necesita una "metrica" válida.';
        }
        if (! in_array($expr['op'] ?? '>', self::OPERADORES, true)) {
            return 'Operador inválido en una hoja de la expresión.';
        }
        if (! isset($expr['valor']) || ! is_numeric($expr['valor'])) {
            return 'Cada hoja necesita un "valor" numérico.';
        }

        return null;
    }
}
