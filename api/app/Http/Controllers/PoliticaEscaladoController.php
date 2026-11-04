<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

/**
 * Políticas de escalado multinivel: niveles ("a los X min sin reconocer, avisa a Y;
 * si sigue sin reconocer, sube al siguiente"). Destino: canal / turno / usuario.
 * Gestión: admin/operador.
 */
class PoliticaEscaladoController extends Controller
{
    public function index(): JsonResponse
    {
        $pols = DB::table('politicas_escalado')->orderBy('nombre')->get();
        $data = $pols->map(function ($p) {
            $p->niveles = DB::table('escalado_niveles as n')
                ->leftJoin('canales_notificacion as c', 'c.id', '=', 'n.canal_id')
                ->leftJoin('turnos_oncall as t', 't.id', '=', 'n.turno_id')
                ->leftJoin('perfiles as u', 'u.id', '=', 'n.perfil_id')
                ->where('n.politica_id', $p->id)->orderBy('n.orden')
                ->get([
                    'n.orden', 'n.espera_min', 'n.destino_tipo', 'n.canal_id', 'n.turno_id', 'n.perfil_id',
                    'c.nombre as canal_nombre', 't.nombre as turno_nombre',
                    'u.nombre as usuario_nombre', 'u.email as usuario_email',
                ]);
            return $p;
        });

        return response()->json(['data' => $data]);
    }

    public function store(Request $request): JsonResponse { return $this->guardar($request, null); }

    public function update(Request $request, int $id): JsonResponse
    {
        if (! DB::table('politicas_escalado')->where('id', $id)->exists()) {
            abort(404);
        }
        return $this->guardar($request, $id);
    }

    public function destroy(int $id): JsonResponse
    {
        DB::table('politicas_escalado')->where('id', $id)->delete();   // cascada a niveles

        return response()->json(null, 204);
    }

    private function guardar(Request $request, ?int $id): JsonResponse
    {
        $data = $request->validate([
            'nombre'                  => ['required', 'string', 'max:150'],
            'activo'                  => ['boolean'],
            'severidad_min'           => ['required', Rule::in(['info', 'warning', 'critical'])],
            'descripcion'             => ['nullable', 'string', 'max:500'],
            'niveles'                 => ['required', 'array', 'min:1'],
            'niveles.*.espera_min'    => ['required', 'integer', 'between:0,10080'],
            'niveles.*.destino_tipo'  => ['required', Rule::in(['canal', 'turno', 'usuario'])],
            'niveles.*.canal_id'      => ['nullable', 'integer', 'exists:canales_notificacion,id'],
            'niveles.*.turno_id'      => ['nullable', 'integer', 'exists:turnos_oncall,id'],
            'niveles.*.perfil_id'     => ['nullable', 'uuid', 'exists:perfiles,id'],
        ]);

        // Coherencia destino↔id.
        foreach ($data['niveles'] as $i => $n) {
            $campo = ['canal' => 'canal_id', 'turno' => 'turno_id', 'usuario' => 'perfil_id'][$n['destino_tipo']];
            if (empty($n[$campo])) {
                throw ValidationException::withMessages([
                    "niveles.$i.$campo" => "El nivel de tipo '{$n['destino_tipo']}' requiere $campo.",
                ]);
            }
        }

        return DB::transaction(function () use ($data, $id) {
            $fila = [
                'nombre'        => $data['nombre'],
                'activo'        => $data['activo'] ?? true,
                'severidad_min' => $data['severidad_min'],
                'descripcion'   => $data['descripcion'] ?? null,
                'updated_at'    => now(),
            ];
            if ($id) {
                DB::table('politicas_escalado')->where('id', $id)->update($fila);
            } else {
                $fila['created_at'] = now();
                $id = DB::table('politicas_escalado')->insertGetId($fila);
            }
            DB::table('escalado_niveles')->where('politica_id', $id)->delete();
            foreach (array_values($data['niveles']) as $orden => $n) {
                DB::table('escalado_niveles')->insert([
                    'politica_id'  => $id,
                    'orden'        => $orden + 1,
                    'espera_min'   => $n['espera_min'],
                    'destino_tipo' => $n['destino_tipo'],
                    'canal_id'     => $n['destino_tipo'] === 'canal' ? $n['canal_id'] : null,
                    'turno_id'     => $n['destino_tipo'] === 'turno' ? $n['turno_id'] : null,
                    'perfil_id'    => $n['destino_tipo'] === 'usuario' ? $n['perfil_id'] : null,
                ]);
            }

            return response()->json(['id' => $id], $id ? 200 : 201);
        });
    }
}
