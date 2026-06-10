<?php

return [

    // Secreto JWT del proyecto Supabase (HS256). En el panel de Supabase:
    // Settings -> API -> JWT Secret. El middleware verifica la firma con él.
    'jwt_secret' => env('SUPABASE_JWT_SECRET'),

    // Audiencia esperada del token (Supabase usa 'authenticated').
    'jwt_audience' => env('SUPABASE_JWT_AUDIENCE', 'authenticated'),

    // Margen de tolerancia (segundos) para desfase de reloj al validar exp/iat.
    'jwt_leeway' => (int) env('SUPABASE_JWT_LEEWAY', 30),

    // URL del proyecto (referencia para el frontend; la API solo valida el JWT).
    'url' => env('SUPABASE_URL'),
];
