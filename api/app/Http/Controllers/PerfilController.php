<?php

namespace App\Http\Controllers;

use App\Models\Perfil;
use App\Support\Alcance;
use App\Support\Auditoria;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Rules\Password;
use Illuminate\Support\Facades\DB;

/**
 * Gestión de usuarios (perfiles). Solo accesible por rol admin (ver rutas).
 * `me` es la excepción: cualquier usuario autenticado consulta su propio perfil.
 */
class PerfilController extends Controller
{
    /** Perfil del usuario autenticado (cualquier rol). */
    public function me(Request $request): JsonResponse
    {
        $perfil = $request->attributes->get('perfil');

        // `acotado` es solo para que la UI no ofrezca lo que la API va a negar.
        // NO es la barrera: la barrera está en cada endpoint (App\Support\Alcance).
        return response()->json(array_merge(
            $perfil ? $perfil->toArray() : [],
            ['acotado' => Alcance::restringido(), 'sitios' => Alcance::sitios()]
        ));
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

        $pag = $q->orderBy('email')->paginate($this->perPage($request));

        // Alcance de cada perfil, para que la lista MUESTRE a qué territoriales está
        // acotado (sin esto el admin no tiene forma de comprobarlo de un vistazo, y
        // "sin sitios = ve todo" pasa desapercibido). Una sola consulta, no una por fila.
        $ids = collect($pag->items())->pluck('id');
        $porPerfil = DB::table('perfil_sitios as ps')
            ->join('sitios as s', 's.id', '=', 'ps.sitio_id')
            ->whereIn('ps.perfil_id', $ids)
            ->get(['ps.perfil_id', 's.id', 's.nombre'])
            ->groupBy('perfil_id');

        $pag->getCollection()->transform(function ($p) use ($porPerfil) {
            $sitios = $porPerfil->get($p->id, collect());
            $p->alcance_sitios = $sitios->map(fn ($s) => ['id' => (int) $s->id, 'nombre' => $s->nombre])->values();

            return $p;
        });

        return response()->json($pag);
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
            'password' => ['required', Password::min(12)->mixedCase()->numbers()->symbols()],
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

        // Los usuarios LDAP traen su identificador del AD (un usuario, p.ej.
        // "emerson.cruz", NO un email): no exigir formato email para no bloquear
        // ediciones legítimas como el cambio de rol. Los locales sí exigen email.
        $reglaEmail = $perfil->origen === 'ldap'
            ? ['sometimes', 'string', 'max:255', Rule::unique('perfiles', 'email')->ignore($perfil->id, 'id')]
            : ['sometimes', 'email', Rule::unique('perfiles', 'email')->ignore($perfil->id, 'id')];

        $data = $request->validate([
            'email'    => $reglaEmail,
            'nombre'   => ['nullable', 'string', 'max:255'],
            'rol'      => ['sometimes', Rule::in(Perfil::ROLES)],
            'activo'   => ['boolean'],
            'password' => ['nullable', Password::min(12)->mixedCase()->numbers()->symbols()],
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

        // No dejar a la app sin administrador LOCAL (cuenta de emergencia si el AD falla).
        $esLocalAdminActivo = $perfil->origen === 'local' && $perfil->rol === 'admin' && $perfil->activo;
        $dejariaDeSerlo = (array_key_exists('rol', $data) && $data['rol'] !== 'admin')
            || (array_key_exists('activo', $data) && $data['activo'] === false);
        if ($esLocalAdminActivo && $dejariaDeSerlo && self::adminsLocalesActivos() <= 1) {
            return response()->json([
                'message' => 'No puedes degradar ni desactivar al último administrador local (cuenta de emergencia).',
            ], 422);
        }

        if (! empty($data['password'])) {
            $perfil->password_hash = Hash::make($data['password']);
        }
        unset($data['password']);

        $perfil->update($data);

        return response()->json($perfil);
    }

    public function destroy(Request $request, string $id): JsonResponse
    {
        $perfil = Perfil::findOrFail($id);

        // Anti-bloqueo: no puedes eliminar tu propia cuenta.
        $actual = $request->attributes->get('perfil');
        if ($actual && $actual->id === $perfil->id) {
            return response()->json(['message' => 'No puedes eliminar tu propia cuenta.'], 422);
        }

        // No dejar la app sin administradores activos.
        if ($perfil->rol === 'admin'
            && Perfil::where('rol', 'admin')->where('activo', true)->count() <= 1) {
            return response()->json(['message' => 'No puedes eliminar al único administrador activo.'], 422);
        }

        // No dejar a la app sin administrador LOCAL (cuenta de emergencia si el AD falla).
        if ($perfil->origen === 'local' && $perfil->rol === 'admin' && $perfil->activo
            && self::adminsLocalesActivos() <= 1) {
            return response()->json([
                'message' => 'No puedes eliminar al último administrador local (cuenta de emergencia).',
            ], 422);
        }

        $perfil->delete();

        return response()->json(null, 204);
    }

    /** Cuenta de administradores LOCALES activos (cuentas de emergencia). */
    private static function adminsLocalesActivos(): int
    {
        return Perfil::where('origen', 'local')
            ->where('rol', 'admin')
            ->where('activo', true)
            ->count();
    }

    /** Sitios asignados a un perfil (su alcance). Vacio = ve toda la entidad. */
    public function sitios(string $id): JsonResponse
    {
        $perfil = Perfil::findOrFail($id);
        $ids = DB::table('perfil_sitios')->where('perfil_id', $perfil->id)
            ->pluck('sitio_id')->map(fn ($x) => (int) $x)->all();

        return response()->json(['data' => $ids]);
    }

    /**
     * Fija el alcance de un perfil (solo admin). Lista vacia = sin restriccion.
     * OJO: a un 'admin' el alcance no le aplica (ver App\Support\Alcance), asi que
     * asignarselo no haria nada; se avisa en vez de crear una falsa sensacion.
     */
    public function asignarSitios(Request $request, string $id): JsonResponse
    {
        $perfil = Perfil::findOrFail($id);
        $data = $request->validate([
            'sitios'   => ['present', 'array'],
            'sitios.*' => ['integer', 'exists:sitios,id'],
        ]);

        if ($perfil->rol === 'admin' && ! empty($data['sitios'])) {
            return response()->json([
                'message' => 'El alcance no aplica a un admin: siempre ve toda la entidad. Cambia su rol a operador o viewer si quieres acotarlo.',
            ], 422);
        }

        $ids = array_values(array_unique(array_map('intval', $data['sitios'])));
        DB::transaction(function () use ($perfil, $ids) {
            DB::table('perfil_sitios')->where('perfil_id', $perfil->id)->delete();
            if ($ids) {
                DB::table('perfil_sitios')->insert(array_map(
                    fn ($sid) => ['perfil_id' => $perfil->id, 'sitio_id' => $sid],
                    $ids
                ));
            }
        });

        Auditoria::registrar('actualizar', 'perfil_alcance', $perfil->id,
            $perfil->email.' -> '.($ids ? 'sitios '.implode(',', $ids) : 'sin restriccion'));

        return response()->json(['data' => $ids]);
    }
}
