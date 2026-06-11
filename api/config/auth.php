<?php

return [
    // La autenticación real la hace el middleware VerifyJwt (JWT propio, sin
    // guards de sesión ni Sanctum). Este archivo se mantiene por compatibilidad
    // del framework; el "user resolver" lo setea el middleware con el Perfil.
    'defaults' => [
        'guard' => 'web',
    ],

    'guards' => [
        'web' => [
            'driver'   => 'session',
            'provider' => 'perfiles',
        ],
    ],

    'providers' => [
        'perfiles' => [
            'driver' => 'eloquent',
            'model'  => App\Models\Perfil::class,
        ],
    ],

    'password_timeout' => 10800,
];
