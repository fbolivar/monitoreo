<?php

namespace App\Http\Controllers;

use App\Models\Perfil;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Str;
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
     * Crea un perfil con contraseña (auth local). El `id` (uuid) se genera aquí.
     */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email'    => ['required', 'email', 'unique:perfiles,email'],
            'nombre'   => ['nullable', 'string', 'max:255'],
            'rol'      => ['required', Rule::in(Perfil::ROLES)],
            'activo'   => ['boolean'],
            'password' => ['required', 'string', 'min:8'],
        ]);

        $perfil = new Perfil([
            'id'     => (string) Str::uuid(),
            'email'  => $data['email'],
            'nombre' => $data['nombre'] ?? null,
            'rol'    => $data['rol'],
            'activo' => $data['activo'] ?? true,
        ]);
        $perfil->password_hash = Hash::make($data['password']);
        $perfil->save();

        return response()->json($perfil, 201);
    }

    public function update(Request $request, string $id): JsonResponse
    {
        $perfil = Perfil::findOrFail($id);

        $data = $request->validate([
            'email'    => ['sometimes', 'email', Rule::unique('perfiles', 'email')->ignore($perfil->id, 'id')],
            'nombre'   => ['nullable', 'string', 'max:255'],
            'rol'      => ['sometimes', Rule::in(Perfil::ROLES)],
            'activo'   => ['boolean'],
            'password' => ['nullable', 'string', 'min:8'],
        ]);

        // Evitar que un admin se bloquee a sí mismo (auto-degradación/desactivación).
        $actual = $request->attributes->get('perfil');
        if ($actual && $actual->id === $perfil->id) {
            if ((array_key_exists('rol', $data) && $data['rol'] !== 'admin')
                || (array_key_exists('activo', $data) && $data['activo'] === false)) {
                return response()->json([
                    'message' => 'No puedes cambiar tu propio rol de administrador ni desactivar tu propia cuenta.',
                ], 422);
            }
        }

        if (! empty($data['password'])) {
            $perfil->password_hash = Hash::make($data['password']);
        }
        unset($data['password']);

        $perfil->update($data);

        return response()->json($perfil);
    }
}
