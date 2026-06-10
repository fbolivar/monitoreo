<?php

namespace App\Http\Controllers;

abstract class Controller
{
    /**
     * Normaliza el tamaño de página (?per_page=), con tope para proteger la BD.
     */
    protected function perPage(\Illuminate\Http\Request $request, int $default = 25, int $max = 200): int
    {
        $n = (int) $request->query('per_page', $default);

        return max(1, min($n, $max));
    }
}
