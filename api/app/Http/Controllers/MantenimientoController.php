<?php

namespace App\Http\Controllers;

use App\Models\Mantenimiento;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;
use App\Support\Alcance;

class MantenimientoController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $q = Mantenimiento::query()->with(['recurso:id,nombre', 'sitio:id,nombre']);
        $this->acotar($q);

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('sitio_id')) {
            $q->where('sitio_id', $request->integer('sitio_id'));
        }
        if ($request->boolean('vigentes')) {
            $q->where('inicio', '<=', now())->where('fin', '>=', now());
        }

        return response()->json($q->orderByDesc('inicio')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        $mant = Mantenimiento::with(['recurso', 'sitio'])->findOrFail($id);
        $this->exigirLectura($mant);

        return response()->json($mant);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate($this->rules());
        $this->validarAmbito($data);
        $this->exigirEscritura($data['recurso_id'] ?? null, $data['sitio_id'] ?? null);
        $data['creado_por'] = optional($request->attributes->get('perfil'))->id;

        return response()->json(Mantenimiento::create($data), 201);
    }

    public function update(Request $request, int $id): JsonResponse
    {
        $mant = Mantenimiento::findOrFail($id);
        $data = $request->validate($this->rules(true));
        $ambito = array_merge($mant->only(['recurso_id', 'sitio_id']), $data);
        $this->validarAmbito($ambito);

        // Ambos extremos: la ventana actual y el ámbito al que la quiere mover.
        $this->exigirEscritura($mant->recurso_id, $mant->sitio_id);
        $this->exigirEscritura($ambito['recurso_id'] ?? null, $ambito['sitio_id'] ?? null);

        $mant->update($data);

        return response()->json($mant);
    }

    /** Una ventana aplica a un recurso, a un sitio, o es global; no a recurso Y sitio. */
    private function validarAmbito(array $d): void
    {
        if (! empty($d['recurso_id']) && ! empty($d['sitio_id'])) {
            throw ValidationException::withMessages([
                'recurso_id' => ['Indique un recurso O un sitio, no ambos (o ninguno para global).'],
            ]);
        }
    }

    public function destroy(int $id): JsonResponse
    {
        $mant = Mantenimiento::findOrFail($id);
        $this->exigirEscritura($mant->recurso_id, $mant->sitio_id);
        $mant->delete();

        return response()->json(null, 204);
    }

    /**
     * Alcance de la lista: ventanas de sus recursos, de sus sitios, y las GLOBALES
     * (sin ámbito), que le afectan aunque no las haya creado él.
     */
    private function acotar($q): void
    {
        $rec = Alcance::recursos();
        if ($rec === null) {
            return;
        }
        $sitios = Alcance::sitios() ?: [-1];
        $q->where(function ($w) use ($rec, $sitios) {
            $w->whereIn('recurso_id', $rec ?: [-1])
              ->orWhereIn('sitio_id', $sitios)
              ->orWhere(fn ($g) => $g->whereNull('recurso_id')->whereNull('sitio_id'));
        });
    }

    private function exigirLectura(Mantenimiento $m): void
    {
        if ($m->recurso_id === null && $m->sitio_id === null) {
            return;   // ventana global: le afecta, puede verla
        }
        $permitida = ($m->recurso_id !== null && Alcance::permiteRecurso($m->recurso_id))
            || ($m->sitio_id !== null && Alcance::permiteSitio($m->sitio_id));
        if (! $permitida) {
            abort(404);
        }
    }

    /**
     * Escritura. Una ventana GLOBAL silencia las alertas de TODA la entidad: un
     * usuario acotado a su territorial no puede crearla ni tocarla (403). Sobre un
     * recurso o sitio ajeno, 404: ni siquiera se le confirma que existe.
     */
    private function exigirEscritura(?int $recursoId, ?int $sitioId): void
    {
        if ($recursoId === null && $sitioId === null) {
            Alcance::exigirAutoridadGlobal();

            return;
        }
        if ($recursoId !== null) {
            Alcance::exigirRecurso($recursoId);
        }
        if ($sitioId !== null) {
            Alcance::exigirSitio($sitioId);
        }
    }

    private function rules(bool $partial = false): array
    {
        $req = $partial ? 'sometimes' : 'required';

        return [
            'recurso_id' => ['nullable', 'integer', 'exists:recursos,id'],
            'sitio_id'   => ['nullable', 'integer', 'exists:sitios,id'],
            'inicio'     => [$req, 'date'],
            'fin'        => [$req, 'date', 'after:inicio'],
            'motivo'     => [$req, 'string', 'max:500'],
        ];
    }
}
