<?php

return [

    // La autenticación real la hace VerifySupabaseJwt (no se usan guards de
    // sesión ni Sanctum). Estos defaults se mantienen por compatibilidad del
    // framework. El "user resolver" se sobreescribe en el middleware con el
    // modelo Perfil correspondiente al `sub` del JWT.
    'defaults' => [
        'guard'     => 'api',
        'passwords' => 'perfiles',
    ],

    'guards' => [
        'api' => [
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

    'passwords' => [
        'perfiles' => [
            'provider' => 'perfiles',
            'table'    => 'password_reset_tokens',
            'expire'   => 60,
            'throttle' => 60,
        ],
    ],

    'password_timeout' => 10800,

];
