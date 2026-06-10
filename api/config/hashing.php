<?php

return [
    // Driver de hashing por defecto.
    'driver' => 'bcrypt',

    'bcrypt' => [
        'rounds' => env('BCRYPT_ROUNDS', 12),
        // verify=false: acepta hashes bcrypt con prefijo $2a$ (los que genera
        // pgcrypto gen_salt('bf')) además de los $2y$ de PHP. Ambos son el mismo
        // algoritmo bcrypt; password_verify los valida igual. Esto permite
        // sembrar contraseñas desde SQL (db/seeds) de forma portable.
        'verify' => false,
        'limit' => null,
    ],

    'argon' => [
        'memory' => 65536,
        'threads' => 1,
        'time' => 4,
        'verify' => true,
    ],

    'rehash_on_login' => true,
];
