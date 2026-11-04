<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

/**
 * Turnos de guardia (on-call): rotación de N días sobre una lista ordenada de
 * participantes. Resuelve quién está de guardia ahora. Gestión: admin/operador.
 */
class TurnoOncallController extends Controller
{
    public function index(): JsonResponse
    {
        $turnos = DB::table('turnos_oncall')->orderBy('nombre')->get();
        $data = $turnos->map(function ($t) {
            $parts = DB::table('turno_participantes as tp')
                ->join('perfiles as p', 'p.id', '=', 'tp.perfil_id')
                ->where('tp.turno_id', $t->id)->orderBy('tp.orden')
                ->get(['tp.perfil_id', 'tp.orden', 'p.nombre', 'p.email']);
            $t->participantes = $parts;
            $t->guardia = $this->guardiaActual($t, $parts);
            return $t;
        });

        return response()->json(['data' => $data]);
    }

    public function guardia(int $id): JsonResponse
    {
        $t = DB::table('turnos_oncall')->find($id);
        if (! $t) {
            abort(404);
        }
        $parts = DB::table('turno_participantes as tp')
            ->join('perfiles as p', 'p.id', '=', 'tp.perfil_id')
            ->where('tp.turno_id', $id)->orderBy('tp.orden')
            ->get(['tp.perfil_id', 'p.nombre', 'p.email']);

        return response()->json(['guardia' => $this->guardiaActual($t, $parts)]);
    }

    public function store(Request $request): JsonResponse
    {
        return $this->guardar($request, null);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        if (! DB::table('turnos_oncall')->where('id', $id)->exists()) {
            abort(404);
        }
        return $this->guardar($request, $id);
    }

    public function destroy(int $id): JsonResponse
    {
        DB::table('turnos_oncall')->where('id', $id)->delete();   // cascada a participantes

        return response()->json(null, 204);
    }

    private function guardar(Request $request, ?int $id): JsonResponse
    {
        $data = $request->validate([
            'nombre'               => ['required', 'string', 'max:150'],
            'activo'               => ['boolean'],
            'rotacion_dias'        => ['required', 'integer', 'between:1,365'],
            'inicio_at'            => ['required', 'date'],
            'participantes'        => ['required', 'array', 'min:1'],
            'participantes.*'      => ['uuid', 'exists:perfiles,id'],
        ]);

        return DB::transaction(function () use ($data, $id) {
            $fila = [
                'nombre'        => $data['nombre'],
                'activo'        => $data['activo'] ?? true,
                'rotacion_dias' => $data['rotacion_dias'],
                'inicio_at'     => Carbon::parse($data['inicio_at']),
                'updated_at'    => now(),
            ];
            if ($id) {
                DB::table('turnos_oncall')->where('id', $id)->update($fila);
            } else {
                $fila['created_at'] = now();
                $id = DB::table('turnos_oncall')->insertGetId($fila);
            }
            DB::table('turno_participantes')->where('turno_id', $id)->delete();
            foreach (array_values($data['participantes']) as $orden => $perfilId) {
                DB::table('turno_participantes')->insert([
                    'turno_id' => $id, 'orden' => $orden, 'perfil_id' => $perfilId,
                ]);
            }

            return response()->json(['id' => $id], $id ? 200 : 201);
        });
    }

    /** Participante de guardia ahora (misma fórmula que el worker). */
    private function guardiaActual($turno, $participantes): ?object
    {
        $n = $participantes->count();
        if ($n === 0 || $turno->rotacion_dias < 1) {
            return null;
        }
        $dias = Carbon::parse($turno->inicio_at)->diffInDays(now(), false);
        $periodos = $dias < 0 ? 0 : intdiv((int) $dias, (int) $turno->rotacion_dias);
        $idx = $periodos % $n;

        return $participantes[$idx] ?? null;
    }
}
