<?php

namespace App\Http\Controllers;

use App\Models\Servicio;
use App\Models\ServicioComponente;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

/**
 * Observabilidad de servicios: correlaciona la latencia/salud de cada salto de
 * una transacción para ubicar el cuello de botella (causa raíz), comparar la
 * experiencia con un objetivo y mostrar el impacto. CRUD + /analisis.
 */
class ServicioController extends Controller
{
    private const PESO = ['down' => 5, 'degraded' => 4, 'unknown' => 3, 'maintenance' => 2, 'up' => 1];

    // Tipos sondeados por SNMP: su latencia es el TIEMPO DE SONDEO (no la latencia
    // de servicio), así que aportan SALUD al análisis, no latencia.
    private const SNMP_TIPOS = ['servidor', 'switch_lan', 'switch_san', 'nas', 'ups'];

    public function index(Request $request): JsonResponse
    {
        $servicios = Servicio::with('componentes')->orderBy('nombre')->get();
        // Resumen ligero (estado, experiencia, cuello) para la lista.
        $datos = $servicios->map(fn ($s) => $this->analizar($s, false));

        return response()->json($datos);
    }

    public function show(int $id): JsonResponse
    {
        $servicio = Servicio::with('componentes')->findOrFail($id);

        return response()->json($servicio);
    }

    /** Análisis de correlación completo de un servicio. */
    public function analisis(int $id): JsonResponse
    {
        $servicio = Servicio::with('componentes')->findOrFail($id);

        return response()->json($this->analizar($servicio, true));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $servicio = DB::transaction(function () use ($data) {
            $s = Servicio::create($this->soloServicio($data));
            $this->sincronizarComponentes($s, $data['componentes'] ?? []);

            return $s;
        });

        return response()->json($servicio->load('componentes'), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $servicio = Servicio::findOrFail($id);
        $data = $request->validate($this->rules(true));
        DB::transaction(function () use ($servicio, $data) {
            $servicio->update($this->soloServicio($data));
            if (array_key_exists('componentes', $data)) {
                $this->sincronizarComponentes($servicio, $data['componentes']);
            }
        });

        return response()->json($servicio->load('componentes'));
    }

    public function destroy(int $id): JsonResponse
    {
        Servicio::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    // ── Análisis ──────────────────────────────────────────────────────
    private function analizar(Servicio $s, bool $detalle): array
    {
        $comps = $s->componentes;
        $ids = $comps->pluck('recurso_id')->filter()->unique()->values();

        // Última latencia + estado + tipo por recurso enlazado.
        $latencias = [];   // recurso_id => latencia_ms
        $estados = [];     // recurso_id => estado_actual
        $nombres = [];     // recurso_id => nombre
        $tiposRec = [];    // recurso_id => tipo_codigo
        if ($ids->isNotEmpty()) {
            $rows = DB::table('recursos as r')
                ->join('tipos_recurso as t', 't.id', '=', 'r.tipo_id')
                ->whereIn('r.id', $ids->all())
                ->get(['r.id', 'r.nombre', 'r.estado_actual', 't.codigo as tipo_codigo']);
            foreach ($rows as $r) {
                $estados[$r->id] = $r->estado_actual;
                $nombres[$r->id] = $r->nombre;
                $tiposRec[$r->id] = $r->tipo_codigo;
            }
            $lat = DB::table('chequeos')
                ->select('recurso_id', DB::raw('max(ts) as ts'))
                ->whereIn('recurso_id', $ids->all())
                ->groupBy('recurso_id')->pluck('ts', 'recurso_id');
            foreach ($lat as $rid => $ts) {
                $latencias[$rid] = DB::table('chequeos')
                    ->where('recurso_id', $rid)->where('ts', $ts)->value('latencia_ms');
            }
        }

        $componentes = [];
        $peorEstado = 'up';
        $cuelloIdx = null;
        $experiencia = null;
        $total = 0;

        foreach ($comps as $i => $c) {
            $estado = $c->recurso_id ? ($estados[$c->recurso_id] ?? 'unknown') : 'unknown';
            $tipoRec = $c->recurso_id ? ($tiposRec[$c->recurso_id] ?? null) : null;
            // Equipos SNMP -> su latencia es tiempo de sondeo, no de servicio: se oculta.
            $infra = in_array($tipoRec, self::SNMP_TIPOS, true);
            $latReal = $c->recurso_id ? ($latencias[$c->recurso_id] ?? null) : null;
            $lat = $infra ? null : ($latReal !== null ? (int) $latReal : null);

            if (self::PESO[$estado] > self::PESO[$peorEstado]) {
                $peorEstado = $estado;
            }
            if ($lat !== null) {
                $total += $lat;
                if ($experiencia === null) {
                    $experiencia = $lat;   // 1er salto con latencia real = experiencia del usuario
                }
            }
            $componentes[] = [
                'orden'          => $c->orden,
                'nombre'         => $c->nombre,
                'tipo'           => $c->tipo,
                'recurso_id'     => $c->recurso_id,
                'recurso_nombre' => $c->recurso_id ? ($nombres[$c->recurso_id] ?? null) : null,
                'estado'         => $estado,
                'latencia_ms'    => $lat,
                'infra'          => $infra,      // salud (SNMP), sin latencia de servicio
                'umbral_ms'      => $c->umbral_ms,
                'supera_umbral'  => $c->umbral_ms !== null && $lat !== null && $lat > $c->umbral_ms,
            ];
        }

        // Cuello de botella: peor estado primero, luego mayor latencia.
        foreach ($componentes as $i => $c) {
            if ($cuelloIdx === null) { $cuelloIdx = $i; continue; }
            $actual = $componentes[$cuelloIdx];
            $mejorEstado = self::PESO[$c['estado']] > self::PESO[$actual['estado']];
            $igualEstadoMasLento = $c['estado'] === $actual['estado']
                && ($c['latencia_ms'] ?? -1) > ($actual['latencia_ms'] ?? -1);
            if ($mejorEstado || $igualEstadoMasLento) {
                $cuelloIdx = $i;
            }
        }

        $cuello = $cuelloIdx !== null ? $componentes[$cuelloIdx] : null;
        $altoImpacto = ($experiencia !== null && $experiencia > $s->objetivo_ms)
            || in_array($peorEstado, ['down', 'degraded'], true);

        // Causa raíz: incidencia abierta del recurso cuello, si la hay.
        $causa = null;
        if ($cuello && $cuello['recurso_id'] && $peorEstado !== 'up') {
            $inc = DB::table('incidencias')
                ->where('recurso_id', $cuello['recurso_id'])->where('estado', '<>', 'resuelta')
                ->orderByDesc('abierta_at')->first(['titulo', 'descripcion']);
            if ($inc) {
                $causa = $inc->descripcion ?: $inc->titulo;
            }
        }

        $resumen = [
            'id'            => $s->id,
            'nombre'        => $s->nombre,
            'descripcion'   => $s->descripcion,
            'objetivo_ms'   => $s->objetivo_ms,
            'impacto_negocio' => $s->impacto_negocio,
            'activo'        => $s->activo,
            'estado'        => $comps->isEmpty() ? 'unknown' : $peorEstado,
            'experiencia_ms' => $experiencia !== null ? (int) $experiencia : null,
            'total_ms'      => $total,
            'alto_impacto'  => $altoImpacto,
            'cuello'        => $cuello ? ['nombre' => $cuello['nombre'], 'latencia_ms' => $cuello['latencia_ms'],
                'recurso_id' => $cuello['recurso_id'], 'estado' => $cuello['estado']] : null,
            'causa'         => $causa,
        ];
        if ($detalle) {
            $resumen['componentes'] = $componentes;
        }

        return $resumen;
    }

    // ── CRUD helpers ──────────────────────────────────────────────────
    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'nombre'              => [$req, 'string', 'max:150'],
            'descripcion'         => ['nullable', 'string', 'max:500'],
            'objetivo_ms'         => ['nullable', 'integer', 'min:1'],
            'impacto_negocio'     => ['nullable', 'string', 'max:1000'],
            'activo'              => ['boolean'],
            'componentes'                 => [$req, 'array', 'min:1'],
            'componentes.*.nombre'        => ['required', 'string', 'max:100'],
            'componentes.*.tipo'          => ['required', Rule::in(['web', 'api', 'gateway', 'cache', 'db', 'externo', 'servicio'])],
            'componentes.*.recurso_id'    => ['nullable', 'integer', 'exists:recursos,id'],
            'componentes.*.umbral_ms'     => ['nullable', 'integer', 'min:0'],
        ];
    }

    private function soloServicio(array $data): array
    {
        return array_intersect_key($data, array_flip(
            ['nombre', 'descripcion', 'objetivo_ms', 'impacto_negocio', 'activo']));
    }

    /** Reemplaza los componentes del servicio con los del payload (orden = índice). */
    private function sincronizarComponentes(Servicio $s, array $componentes): void
    {
        $s->componentes()->delete();
        foreach (array_values($componentes) as $i => $c) {
            ServicioComponente::create([
                'servicio_id' => $s->id,
                'orden'       => $i,
                'nombre'      => $c['nombre'],
                'tipo'        => $c['tipo'],
                'recurso_id'  => $c['recurso_id'] ?? null,
                'umbral_ms'   => $c['umbral_ms'] ?? null,
            ]);
        }
    }
}
