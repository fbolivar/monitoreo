<?php

namespace App\Http\Controllers;

use App\Models\Incidencia;
use App\Support\Auditoria;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * Lectura (filtros: recurso_id, estado, severidad, desde, hasta sobre `abierta_at`),
 * gestión (reconocer/resolver) y bitácora de notas del operador.
 */
class IncidenciaController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'recurso_id' => ['nullable', 'integer'],
            'estado'     => ['nullable', 'in:abierta,reconocida,resuelta'],
            'severidad'  => ['nullable', 'in:info,warning,critical'],
            'desde'      => ['nullable', 'date'],
            'hasta'      => ['nullable', 'date'],
        ]);

        $q = Incidencia::query()->with(['recurso:id,nombre', 'reconocidaPor:id,nombre,email']);

        if ($request->filled('recurso_id')) {
            $q->where('recurso_id', $request->integer('recurso_id'));
        }
        if ($request->filled('estado')) {
            $q->where('estado', $request->query('estado'));
        }
        if ($request->filled('severidad')) {
            $q->where('severidad', $request->query('severidad'));
        }
        if ($request->filled('desde')) {
            $q->where('abierta_at', '>=', $request->date('desde'));
        }
        if ($request->filled('hasta')) {
            $q->where('abierta_at', '<=', $request->date('hasta'));
        }

        return response()->json($q->orderByDesc('abierta_at')->paginate($this->perPage($request)));
    }

    public function show(int $id): JsonResponse
    {
        return response()->json(
            Incidencia::with(['recurso', 'reconocidaPor:id,nombre,email'])->findOrFail($id)
        );
    }

    /** Reconocer una incidencia (admin/operador). El worker la sigue considerando
     *  abierta (estado <> resuelta), así que no abre una nueva. */
    public function reconocer(Request $request, int $id): JsonResponse
    {
        $inc = Incidencia::findOrFail($id);
        if ($inc->estado === 'resuelta') {
            return response()->json(['message' => 'La incidencia ya está resuelta.'], 422);
        }

        $inc->update([
            'estado'         => 'reconocida',
            'reconocida_at'  => $inc->reconocida_at ?? now(),
            'reconocida_por' => $inc->reconocida_por ?? optional($request->attributes->get('perfil'))->id,
        ]);

        return response()->json($inc->load(['recurso:id,nombre', 'reconocidaPor:id,nombre,email']));
    }

    /** Resolver una incidencia manualmente (admin/operador). Si el recurso sigue
     *  caído, el worker abrirá una nueva incidencia en el próximo chequeo. */
    public function resolver(int $id): JsonResponse
    {
        $inc = Incidencia::findOrFail($id);
        if ($inc->estado === 'resuelta') {
            return response()->json(['message' => 'La incidencia ya está resuelta.'], 422);
        }

        $inc->update(['estado' => 'resuelta', 'resuelta_at' => now()]);

        return response()->json($inc->load(['recurso:id,nombre', 'reconocidaPor:id,nombre,email']));
    }

    /** Bitácora de la incidencia: notas del operador, en orden cronológico (lectura). */
    public function notas(int $id): JsonResponse
    {
        Incidencia::findOrFail($id);   // 404 si la incidencia no existe

        $notas = DB::table('incidencia_notas')
            ->where('incidencia_id', $id)
            ->orderBy('created_at')
            ->get(['id', 'autor_email', 'nota', 'created_at']);

        return response()->json(['data' => $notas]);
    }

    /**
     * Añade una nota (admin/operador). Es lo que convierte una incidencia en
     * historia útil: qué se vio, qué se hizo, qué queda pendiente para el relevo.
     */
    public function agregarNota(Request $request, int $id): JsonResponse
    {
        $inc = Incidencia::findOrFail($id);
        $data = $request->validate([
            'nota' => ['required', 'string', 'min:1', 'max:4000'],
        ]);

        $perfil = $request->attributes->get('perfil');
        $nota = DB::table('incidencia_notas')->insertGetId([
            'incidencia_id' => $inc->id,
            'perfil_id'     => optional($perfil)->id,
            'autor_email'   => optional($perfil)->email,
            'nota'          => trim($data['nota']),
            'created_at'    => now(),
        ]);

        Auditoria::registrar('crear', 'incidencia_nota', $nota, 'Nota en incidencia '.$inc->id);

        return response()->json(
            DB::table('incidencia_notas')->where('id', $nota)
                ->first(['id', 'autor_email', 'nota', 'created_at']),
            201
        );
    }
}
