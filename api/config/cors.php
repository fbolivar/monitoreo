<?php

return [

    'paths' => ['api/*', 'up'],

    'allowed_methods' => ['*'],

    // En producción, restringir al dominio del frontend Angular.
    'allowed_origins' => explode(',', env('CORS_ALLOWED_ORIGINS', '*')),

    'allowed_origins_patterns' => [],

    'allowed_headers' => ['*'],

    'exposed_headers' => [],

    'max_age' => 0,

    'supports_credentials' => false,

];
