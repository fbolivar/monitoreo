<?php

namespace App\Http\Controllers;

use App\Models\Perfil;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

/**
 * Gestión de usuarios (perfiles). Solo accesible por rol admin (ver rutas).
 * `me` es la excepción: cualquier usuario autenticado consulta su propio perfil.
 */
class PerfilController extends Controller
{
    /** Perfil del usuario autenticado (cualquier rol). */
    public function me(Request $request): JsonResponse
    {
        return response()->json($request->attributes->get('perfil'));
    }

    public function index(Request $request): JsonResponse
    {
        $q = Perfil::query();

        if ($request->filled('rol')) {
            $q->where('rol', $request->query('rol'));
        }
        if ($request->filled('activo')) {
            $q->where('activo', $request->boolean('activo'));
        }

        return response()->json($q->orderBy('email')->paginate($this->perPage($request)));
    }

    public function show(string $id): JsonResponse
    {
        return response()->json(Perfil::findOrFail($id));
    }

    /**
     * Crea un perfil. El `id` debe ser el uuid del usuario en Supabase Auth.
     */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'id'     => ['required', 'uuid', 'unique:perfiles,id'],
            'email'  => ['required', 'email', 'unique:perfiles,email'],
            'nombre' => ['nullable', 'string', 'max:255'],
            'rol'    => ['required', Rule::in(Perfil::ROLES)],
            'activo' => ['boolean'],
        ]);

        return response()->json(Perfil::create($data), 201);
    }

    public function update(Request $request, string $id): JsonResponse
    {
        $perfil = Perfil::findOrFail($id);

        $data = $request->validate([
            'email'  => ['sometimes', 'email', Rule::unique('perfiles', 'email')->ignore($perfil->id, 'id')],
            'nombre' => ['nullable', 'string', 'max:255'],
            'rol'    => ['sometimes', Rule::in(Perfil::ROLES)],
            'activo' => ['boolean'],
        ]);

        $perfil->update($data);

        return response()->json($perfil);
    }
}
