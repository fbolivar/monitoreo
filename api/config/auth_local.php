<?php

return [
    // Secreto para firmar/validar el JWT propio de la aplicación (HS256).
    // Generar fuerte:  openssl rand -hex 32
    'jwt_secret' => env('AUTH_JWT_SECRET'),

    // Vigencia del token en segundos (por defecto 12 horas).
    'ttl' => (int) env('AUTH_JWT_TTL', 43200),

    // Margen de tolerancia de reloj al validar exp/iat.
    'leeway' => (int) env('AUTH_JWT_LEEWAY', 30),

    // Bloqueo por fuerza bruta: tras `max_intentos` fallos en `lockout_min`
    // minutos para el mismo usuario, se rechaza el login temporalmente.
    'max_intentos' => (int) env('AUTH_MAX_INTENTOS', 5),
    'lockout_min'  => (int) env('AUTH_LOCKOUT_MIN', 15),
];
