<?php

namespace App\Http\Controllers;

use App\Models\DescubrimientoCandidato;
use App\Models\DescubrimientoEscaneo;
use App\Models\Recurso;
use App\Models\TipoRecurso;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

/**
 * Auto-descubrimiento de red. La API encola escaneos (estado 'pendiente') que el
 * worker ejecuta (ping sweep + SNMP); luego lista los candidatos y permite darlos
 * de alta como recurso con un clic o descartarlos.
 */
class DescubrimientoController extends Controller
{
    /** Lista de escaneos (más recientes primero) con conteo de candidatos. */
    public function index(Request $request): JsonResponse
    {
        $escaneos = DescubrimientoEscaneo::query()
            ->withCount([
                'candidatos',
                'candidatos as candidatos_nuevos' => fn ($q) => $q->where('estado', 'nuevo'),
            ])
            ->orderByDesc('id')
            ->paginate($this->perPage($request, 20));

        return response()->json($escaneos);
    }

    /** Detalle de un escaneo con sus candidatos. */
    public function show(int $id): JsonResponse
    {
        $escaneo = DescubrimientoEscaneo::findOrFail($id);
        $candidatos = $escaneo->candidatos()
            ->orderByRaw("CASE estado WHEN 'nuevo' THEN 0 WHEN 'existente' THEN 1 WHEN 'agregado' THEN 2 ELSE 3 END")
            ->orderBy('ip')
            ->get();

        $data = $escaneo->toArray();
        $data['candidatos'] = $candidatos;

        return response()->json($data);
    }

    /** Encola un nuevo barrido (lo ejecuta el worker). */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'subred'         => ['required', 'string', 'max:64'],
            'snmp_version'   => ['nullable', Rule::in(['1', '2c'])],
            'snmp_community' => ['nullable', 'string', 'max:255'],
        ]);

        $this->validarSubred($data['subred']);

        $escaneo = new DescubrimientoEscaneo([
            'subred'       => trim($data['subred']),
            'snmp_version' => $data['snmp_version'] ?? '2c',
            'perfil_id'    => $request->user()->id ?? null,
        ]);

        if (! empty($data['snmp_community'])) {
            $escaneo->setSecretosPlanos(['snmp_community' => $data['snmp_community']]);
        }
        $escaneo->save();

        return response()->json($escaneo->fresh(), 201);
    }

    /** Elimina un escaneo (y sus candidatos por cascada). */
    public function destroy(int $id): JsonResponse
    {
        DescubrimientoEscaneo::findOrFail($id)->delete();

        return response()->json(null, 204);
    }

    /** Da de alta un candidato como recurso (alta con un clic, editable). */
    public function agregar(Request $request, int $candidatoId): JsonResponse
    {
        $cand = DescubrimientoCandidato::findOrFail($candidatoId);

        if ($cand->estado === 'agregado') {
            return response()->json(['message' => 'El candidato ya fue agregado.'], 409);
        }
        if ($cand->recurso_id || Recurso::where('hostname', $cand->ip)->exists()) {
            return response()->json(['message' => 'Ya existe un recurso con esa IP.'], 409);
        }

        $data = $request->validate([
            'tipo_id'            => ['required', 'integer', 'exists:tipos_recurso,id'],
            'sitio_id'           => ['nullable', 'integer', 'exists:sitios,id'],
            'nombre'             => ['required', 'string', 'max:255'],
            'intervalo_segundos' => ['nullable', 'integer', 'between:5,86400'],
            'parametros'         => ['nullable', 'array'],
            'secretos'           => ['nullable', 'array'],
        ]);

        $recurso = DB::transaction(function () use ($cand, $data) {
            $recurso = new Recurso([
                'tipo_id'            => $data['tipo_id'],
                'sitio_id'           => $data['sitio_id'] ?? null,
                'nombre'             => $data['nombre'],
                'hostname'           => $cand->ip,
                'parametros'         => $data['parametros'] ?? [],
                'intervalo_segundos' => $data['intervalo_segundos'] ?? null,
                'activo'             => true,
            ]);
            if (! empty($data['secretos'])) {
                $recurso->setSecretosPlanos($data['secretos']);
            }
            $recurso->save();

            $cand->update(['estado' => 'agregado', 'recurso_id' => $recurso->id]);

            return $recurso;
        });

        return response()->json($recurso->fresh(['tipo', 'sitio']), 201);
    }

    /** Marca un candidato como descartado (no interesa monitorearlo). */
    public function descartar(int $candidatoId): JsonResponse
    {
        $cand = DescubrimientoCandidato::findOrFail($candidatoId);

        if ($cand->estado === 'agregado') {
            return response()->json(['message' => 'No se puede descartar un candidato ya agregado.'], 409);
        }
        $cand->update(['estado' => 'descartado']);

        return response()->json($cand);
    }

    /** Sugiere el tipo_id (por código) a partir del tipo_sugerido del candidato. */
    public function tiposSugeridos(): JsonResponse
    {
        return response()->json(
            TipoRecurso::orderBy('nombre')->get(['id', 'codigo', 'nombre'])
        );
    }

    private function validarSubred(string $subred): void
    {
        $subred = trim($subred);

        // IP suelta o CIDR. Validamos formato y tope de tamaño (/22 = 1024 hosts).
        if (str_contains($subred, '/')) {
            [$ip, $masc] = explode('/', $subred, 2);
            if (! filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4) || ! ctype_digit($masc)) {
                abort(422, 'Subred inválida. Use formato CIDR, p.ej. 192.168.10.0/24.');
            }
            $masc = (int) $masc;
            if ($masc < 22 || $masc > 32) {
                abort(422, 'Prefijo fuera de rango: use entre /22 (1024 hosts) y /32.');
            }
        } elseif (! filter_var($subred, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
            abort(422, 'IP o subred inválida.');
        }
    }
}
