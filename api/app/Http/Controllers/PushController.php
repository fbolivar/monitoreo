<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/** Web Push / PWA (#11): clave pública VAPID y registro de suscripciones del navegador. */
class PushController extends Controller
{
    /** Clave pública VAPID (lectura; el frontend la usa para suscribir). */
    public function vapid(): JsonResponse
    {
        return response()->json(['publicKey' => config('push.vapid_public', '')]);
    }

    /** Registra/actualiza la suscripción del navegador del usuario autenticado. */
    public function suscribir(Request $request): JsonResponse
    {
        $data = $request->validate([
            'endpoint'     => ['required', 'string'],
            'keys'         => ['required', 'array'],
            'keys.p256dh'  => ['required', 'string'],
            'keys.auth'    => ['required', 'string'],
        ]);

        DB::table('push_suscripciones')->updateOrInsert(
            ['endpoint' => $data['endpoint']],
            [
                'perfil_id'  => optional($request->attributes->get('perfil'))->id,
                'p256dh'     => $data['keys']['p256dh'],
                'auth'       => $data['keys']['auth'],
                'user_agent' => substr($request->userAgent() ?? '', 0, 255),
                'created_at' => now(),
            ]
        );

        return response()->json(['ok' => true], 201);
    }

    public function desuscribir(Request $request): JsonResponse
    {
        $endpoint = $request->validate(['endpoint' => ['required', 'string']])['endpoint'];
        DB::table('push_suscripciones')->where('endpoint', $endpoint)->delete();

        return response()->json(null, 204);
    }
}
