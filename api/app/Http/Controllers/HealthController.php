<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;

/**
 * Endpoint de salud (público, sin JWT) para que SIMON se vigile a sí mismo vía el
 * chequeo sintético: prueba nginx + php-fpm + la API + la conexión a PostgreSQL
 * (SELECT 1). No expone detalles sensibles (solo ok/degraded). 503 si la BD cae.
 */
class HealthController extends Controller
{
    public function check(): JsonResponse
    {
        try {
            DB::select('select 1');
        } catch (\Throwable $e) {
            return response()->json(['status' => 'degraded', 'db' => false], 503);
        }

        return response()->json(['status' => 'ok', 'db' => true]);
    }
}
