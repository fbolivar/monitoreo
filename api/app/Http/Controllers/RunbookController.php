<?php

namespace App\Http\Controllers;

use App\Models\Runbook;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

/** Auto-remediación / runbooks (#5). CRUD (admin/operador) + historial de ejecuciones. */
class RunbookController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        return response()->json(Runbook::query()->orderBy('nombre')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        $rb = Runbook::findOrFail($id);
        $data = $rb->toArray();
        $data['tiene_secretos'] = $rb->tieneSecretos();
        $data['ejecuciones'] = DB::table('runbook_ejecuciones')
            ->where('runbook_id', $id)->orderByDesc('ts')->limit(20)->get();

        return response()->json($data);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $secretos = $data['secretos'] ?? null;
        unset($data['secretos']);

        $rb = new Runbook($data);
        if ($request->has('secretos')) {
            $rb->setSecretosPlanos($secretos);
        }
        $rb->save();

        return response()->json($rb, 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $rb = Runbook::findOrFail($id);
        $data = $request->validate($this->rules(true));
        if ($request->has('secretos')) {
            $rb->setSecretosPlanos($data['secretos'] ?? null);
        }
        unset($data['secretos']);
        $rb->update($data);

        return response()->json($rb);
    }

    public function destroy(int $id): JsonResponse
    {
        Runbook::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'nombre'            => [$req, 'string', 'max:255'],
            'descripcion'       => ['nullable', 'string'],
            'activo'            => ['boolean'],
            'trigger_tipo_id'   => ['nullable', 'integer'],
            'trigger_severidad' => ['nullable', Rule::in(['info', 'warning', 'critical'])],
            'trigger_match'     => ['nullable', 'string', 'max:255'],
            'accion'            => [$req, 'array'],
            'accion.tipo'       => [$req, Rule::in(['webhook', 'ssh'])],
            // Defensa en profundidad: el worker EJECUTA esto (webhook saliente o
            // comando SSH). Validar forma y esquema reduce el vector RCE/SSRF.
            'accion.url'        => ['nullable', 'required_if:accion.tipo,webhook', 'url:http,https', 'max:2048'],
            'accion.comando'    => ['nullable', 'required_if:accion.tipo,ssh', 'string', 'max:4096'],
            'cooldown_seg'      => ['nullable', 'integer', 'min:0'],
            'secretos'          => ['nullable', 'array'],
        ];
    }
}
