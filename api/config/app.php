<?php

return [

    'name' => env('APP_NAME', 'Monitoreo TI API'),

    'env' => env('APP_ENV', 'production'),

    'debug' => (bool) env('APP_DEBUG', false),

    'url' => env('APP_URL', 'http://localhost'),

    'timezone' => env('APP_TIMEZONE', 'America/Bogota'),

    'locale' => env('APP_LOCALE', 'es'),

    'fallback_locale' => env('APP_FALLBACK_LOCALE', 'en'),

    'faker_locale' => env('APP_FAKER_LOCALE', 'es_ES'),

    // Clave de cifrado interna de Laravel (sesiones, etc.). No es la de secretos.
    'cipher' => 'AES-256-CBC',

    'key' => env('APP_KEY'),

    'previous_keys' => [
        ...array_filter(
            explode(',', env('APP_PREVIOUS_KEYS', ''))
        ),
    ],

    // ── Clave maestra de cifrado de SECRETOS de recursos/canales ──────
    // Se usa con pgcrypto (cifrar_secreto/descifrar_secreto). NUNCA se
    // almacena en la base de datos. Debe coincidir con el APP_CRYPTO_KEY
    // con el que se cifró el seed/datos.
    'crypto_key' => env('APP_CRYPTO_KEY'),

    'maintenance' => [
        'driver' => env('APP_MAINTENANCE_DRIVER', 'file'),
        'store'  => env('APP_MAINTENANCE_STORE', 'database'),
    ],

];
