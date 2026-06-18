<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * Ingesta PÚBLICA (sin JWT): agentes ligeros (#8) y APM/RUM (#13).
 * - /ingest/agente: autenticado por token de agente (cabecera X-Agent-Token).
 * - /ingest/rum, /ingest/span: beacon del navegador / OTel (token opcional).
 */
class IngestController extends Controller
{
    public function agente(Request $request): JsonResponse
    {
        $token = $request->header('X-Agent-Token');
        if (! $token) {
            return response()->json(['error' => 'falta token'], 401);
        }
        $agente = DB::table('agentes')
            ->where('token_hash', hash('sha256', $token))
            ->where('activo', true)->first();
        if (! $agente) {
            return response()->json(['error' => 'token inválido'], 401);
        }

        $data = $request->validate([
            'hostname'   => ['nullable', 'string'],
            'so'         => ['nullable', 'string'],
            'version'    => ['nullable', 'string'],
            'metricas'   => ['nullable', 'array'],
            'inventario' => ['nullable', 'array'],
        ]);

        DB::table('agentes')->where('id', $agente->id)->update([
            'hostname'   => $data['hostname'] ?? $agente->hostname,
            'so'         => $data['so'] ?? $agente->so,
            'version'    => $data['version'] ?? $agente->version,
            'last_seen'  => now(),
            'inventario' => json_encode($data['inventario'] ?? null),
        ]);

        // Métricas -> tabla metricas (si el agente está asociado a un recurso).
        if ($agente->recurso_id && ! empty($data['metricas'])) {
            $filas = [];
            foreach ($data['metricas'] as $nombre => $valor) {
                if (! is_numeric($valor)) {
                    continue;
                }
                $unidad = str_starts_with((string) $nombre, 'disco') || in_array($nombre, ['cpu', 'mem'], true) ? '%' : null;
                $filas[] = [
                    'recurso_id' => $agente->recurso_id,
                    'metrica'    => substr((string) $nombre, 0, 60),
                    'valor'      => (float) $valor,
                    'unidad'     => $unidad,
                    'ts'         => now(),
                ];
            }
            if ($filas) {
                DB::table('metricas')->insert($filas);
            }
        }

        return response()->json(['ok' => true]);
    }

    public function rum(Request $request): JsonResponse
    {
        $data = $request->validate([
            'url'       => ['nullable', 'string', 'max:500'],
            'tipo'      => ['nullable', 'string', 'max:30'],
            'valor_ms'  => ['nullable', 'numeric'],
            'navegador' => ['nullable', 'string', 'max:200'],
            'sitio'     => ['nullable', 'string', 'max:100'],
        ]);

        DB::table('rum_eventos')->insert([
            'url'       => $data['url'] ?? null,
            'tipo'      => $data['tipo'] ?? 'pageload',
            'valor_ms'  => $data['valor_ms'] ?? null,
            'navegador' => substr($request->userAgent() ?? ($data['navegador'] ?? ''), 0, 200),
            'sitio'     => $data['sitio'] ?? null,
            'ts'        => now(),
        ]);

        return response()->json(['ok' => true]);
    }

    public function span(Request $request): JsonResponse
    {
        $data = $request->validate([
            'trace_id'  => ['nullable', 'string', 'max:64'],
            'span_id'   => ['nullable', 'string', 'max:64'],
            'parent_id' => ['nullable', 'string', 'max:64'],
            'nombre'    => ['nullable', 'string', 'max:200'],
            'servicio'  => ['nullable', 'string', 'max:100'],
            'dur_ms'    => ['nullable', 'numeric'],
        ]);

        DB::table('spans')->insert([
            'trace_id'  => $data['trace_id'] ?? null,
            'span_id'   => $data['span_id'] ?? null,
            'parent_id' => $data['parent_id'] ?? null,
            'nombre'    => $data['nombre'] ?? null,
            'servicio'  => $data['servicio'] ?? null,
            'dur_ms'    => $data['dur_ms'] ?? null,
            'ts'        => now(),
        ]);

        return response()->json(['ok' => true]);
    }
}
