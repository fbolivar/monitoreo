<?php

use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return response()->json([
        'servicio' => 'Monitoreo de Disponibilidad de TI — API',
        'estado'   => 'ok',
        'docs'     => '/api (requiere JWT de Supabase)',
    ]);
});
