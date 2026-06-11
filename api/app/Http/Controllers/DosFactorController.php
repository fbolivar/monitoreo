<?php

namespace App\Http\Controllers;

use App\Support\Totp;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/** Gestión del 2FA (TOTP) del usuario autenticado. */
class DosFactorController extends Controller
{
    /** Genera (o regenera) el secreto y devuelve el URI para la app autenticadora. */
    public function iniciar(Request $request): JsonResponse
    {
        $perfil = $request->user();
        if ($perfil->origen !== 'local') {
            return response()->json(['message' => 'El 2FA solo aplica a cuentas locales.'], 422);
        }

        $secreto = Totp::generarSecreto();
        $perfil->totp_secret = $secreto;
        $perfil->totp_activo = false; // se confirma con activar()
        $perfil->save();

        return response()->json([
            'secret' => $secreto,
            'uri'    => Totp::uri($secreto, $perfil->email),
        ]);
    }

    /** Confirma el código de la app y activa el 2FA. */
    public function activar(Request $request): JsonResponse
    {
        $data = $request->validate(['codigo' => ['required', 'string']]);
        $perfil = $request->user();

        if (! $perfil->totp_secret) {
            return response()->json(['message' => 'Primero inicia la configuración del 2FA.'], 422);
        }
        if (! Totp::verificar($perfil->totp_secret, $data['codigo'])) {
            return response()->json(['message' => 'Código inválido. Intenta de nuevo.'], 422);
        }

        $perfil->totp_activo = true;
        $perfil->save();

        return response()->json(['totp_activo' => true]);
    }

    /** Desactiva el 2FA (requiere un código válido). */
    public function desactivar(Request $request): JsonResponse
    {
        $data = $request->validate(['codigo' => ['required', 'string']]);
        $perfil = $request->user();

        if (! $perfil->totp_activo
            || ! Totp::verificar((string) $perfil->totp_secret, $data['codigo'])) {
            return response()->json(['message' => 'Código inválido.'], 422);
        }

        $perfil->totp_activo = false;
        $perfil->totp_secret = null;
        $perfil->save();

        return response()->json(['totp_activo' => false]);
    }
}
