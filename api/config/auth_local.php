<?php

return [
    // Secreto para firmar/validar el JWT propio de la aplicación (HS256).
    // Generar fuerte:  openssl rand -hex 32
    'jwt_secret' => env('AUTH_JWT_SECRET'),

    // Vigencia del token en segundos (por defecto 12 horas).
    'ttl' => (int) env('AUTH_JWT_TTL', 43200),

    // Margen de tolerancia de reloj al validar exp/iat.
    'leeway' => (int) env('AUTH_JWT_LEEWAY', 30),
];
