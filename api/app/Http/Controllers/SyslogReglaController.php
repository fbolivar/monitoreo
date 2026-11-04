<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

/** Reglas syslog patrón→incidencia (abrir/cerrar). Gestión: admin/operador. */
class SyslogReglaController extends Controller
{
    public function index(): JsonResponse
    {
        return response()->json(['data' => DB::table('syslog_reglas')->orderBy('nombre')->get()]);
    }

    public function store(Request $request): JsonResponse { return $this->guardar($request, null); }

    public function update(Request $request, int $id): JsonResponse
    {
        if (! DB::table('syslog_reglas')->where('id', $id)->exists()) {
            abort(404);
        }
        return $this->guardar($request, $id);
    }

    public function destroy(int $id): JsonResponse
    {
        DB::table('syslog_reglas')->where('id', $id)->delete();

        return response()->json(null, 204);
    }

    private function guardar(Request $request, ?int $id): JsonResponse
    {
        $data = $request->validate([
            'nombre'    => ['required', 'string', 'max:150'],
            'activo'    => ['boolean'],
            'campo'     => ['required', Rule::in(['mensaje', 'app', 'hostname'])],
            'patron'    => ['required', 'string', 'max:500'],
            'accion'    => ['required', Rule::in(['abrir', 'cerrar'])],
            'severidad' => ['nullable', Rule::in(['warning', 'critical'])],
            'clave'     => ['required', 'string', 'max:60'],
            'notificar' => ['boolean'],
        ]);
        if ($data['accion'] === 'abrir' && empty($data['severidad'])) {
            throw ValidationException::withMessages(['severidad' => 'Una regla de abrir requiere severidad.']);
        }
        // Validar que el patrón sea un regex compilable (evita romper el receptor).
        if (@preg_match('/'.str_replace('/', '\/', $data['patron']).'/', '') === false) {
            throw ValidationException::withMessages(['patron' => 'El patrón no es un regex válido.']);
        }

        $fila = [
            'nombre' => $data['nombre'], 'activo' => $data['activo'] ?? true,
            'campo' => $data['campo'], 'patron' => $data['patron'], 'accion' => $data['accion'],
            'severidad' => $data['accion'] === 'abrir' ? $data['severidad'] : null,
            'clave' => $data['clave'], 'notificar' => $data['notificar'] ?? true,
            'updated_at' => now(),
        ];
        if ($id) {
            DB::table('syslog_reglas')->where('id', $id)->update($fila);
        } else {
            $fila['created_at'] = now();
            $id = DB::table('syslog_reglas')->insertGetId($fila);
        }

        return response()->json(['id' => $id], $id ? 200 : 201);
    }
}
