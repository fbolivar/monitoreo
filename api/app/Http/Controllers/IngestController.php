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

        // Puente con Cumplimiento (#7): guarda un snapshot de configuración del
        // servidor (SO/discos/servicios) en config_respaldos —solo si cambió—,
        // para que el motor de cumplimiento pueda evaluar políticas de servidor.
        if ($agente->recurso_id) {
            $snap = $this->snapshotConfig($data);
            if ($snap !== '') {
                $hash = hash('sha256', $snap);
                $last = DB::table('config_respaldos')->where('recurso_id', $agente->recurso_id)
                    ->orderByDesc('id')->first();
                if (! $last || $last->hash !== $hash) {
                    DB::table('config_respaldos')->insert([
                        'recurso_id' => $agente->recurso_id,
                        'hash'       => $hash,
                        'bytes'      => strlen($snap),
                        'cambio'     => (bool) $last,
                        'diff'       => $last ? $this->diffLineas($last->contenido, $snap) : null,
                        'contenido'  => $snap,
                    ]);
                }
            }
        }

        return response()->json(['ok' => true]);
    }

    /** Construye un snapshot de configuración determinista del servidor desde el inventario del agente. */
    private function snapshotConfig(array $data): string
    {
        $inv = $data['inventario'] ?? [];
        if (empty($inv['discos']) && empty($inv['servicios']) && empty($inv['servicios_vigilados'])) {
            return '';
        }
        $l = ['# Snapshot de configuración del servidor (agente SIMON)'];
        $l[] = 'SO: '.($data['so'] ?? '');
        $l[] = 'Agente version: '.($data['version'] ?? '');

        $l[] = '';
        $l[] = '[Discos]';
        $discos = $inv['discos'] ?? [];
        usort($discos, fn ($a, $b) => strcmp($a['montaje'] ?? '', $b['montaje'] ?? ''));
        foreach ($discos as $d) {
            $l[] = 'disco '.($d['montaje'] ?? '?').' total='.($d['total_gb'] ?? '?').'GB';
        }

        // Servicios vigilados (estado explícito running/stopped/absent): base estable
        // para cumplimiento en ambos sentidos. Si el agente no los envía, se cae a los "no activos".
        $vig = $inv['servicios_vigilados'] ?? [];
        if (! empty($vig)) {
            usort($vig, fn ($a, $b) => strcmp($a['nombre'] ?? '', $b['nombre'] ?? ''));
            $l[] = '';
            $l[] = '[Servicios vigilados]';
            foreach ($vig as $s) {
                $l[] = 'servicio: '.($s['nombre'] ?? '?').' = '.($s['estado'] ?? '?');
            }
        } else {
            $svcs = $inv['servicios'] ?? [];
            usort($svcs, fn ($a, $b) => strcmp($a['nombre'] ?? '', $b['nombre'] ?? ''));
            $l[] = '';
            $l[] = '[Servicios no activos]';
            foreach ($svcs as $s) {
                $l[] = 'servicio: '.($s['nombre'] ?? '?').' = '.($s['estado'] ?? '?');
            }
        }

        return implode("\n", $l);
    }

    /** Diff simple (líneas añadidas/quitadas) para mostrar en la sección "Respaldos". */
    private function diffLineas(string $old, string $new): string
    {
        $o = array_flip(explode("\n", $old));
        $n = array_flip(explode("\n", $new));
        $out = [];
        foreach (array_diff_key($n, $o) as $line => $_) {
            if (trim((string) $line) !== '') {
                $out[] = '+ '.$line;
            }
        }
        foreach (array_diff_key($o, $n) as $line => $_) {
            if (trim((string) $line) !== '') {
                $out[] = '- '.$line;
            }
        }

        return implode("\n", array_slice($out, 0, 200));
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
