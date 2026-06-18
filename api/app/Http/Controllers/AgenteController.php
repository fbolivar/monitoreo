<?php

namespace App\Http\Controllers;

use App\Models\Agente;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

/** Gestión de agentes ligeros (#8). Solo admin. El token se muestra UNA vez al crear. */
class AgenteController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        return response()->json(Agente::query()->orderByDesc('last_seen')->paginate($this->perPage($request)));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'nombre'     => ['required', 'string', 'max:255'],
            'recurso_id' => ['nullable', 'integer'],
        ]);

        $token = Str::random(40);
        $agente = Agente::create([
            'nombre'     => $data['nombre'],
            'recurso_id' => $data['recurso_id'] ?? null,
            'token_hash' => hash('sha256', $token),
            'activo'     => true,
        ]);

        // El token se devuelve SOLO aquí (después solo se guarda su hash).
        return response()->json(['agente' => $agente, 'token' => $token], 201);
    }

    public function destroy(int $id): JsonResponse
    {
        Agente::findOrFail($id)->delete();

        return response()->json(null, 204);
    }
}
