<?php

// Módulo de respaldo .pnnc (formato propio PNNC). Genera y exporta backups de la
// BD desde la aplicación (solo admin). La restauración es por shell en el servidor.
return [
    // Carpeta donde se generan/guardan los .pnnc. Debe ser escribible por www-data.
    'dir' => env('RESPALDO_PNNC_DIR', '/var/backups/monitoreo/pnnc'),

    // Cuántos .pnnc conservar (rotación; los más antiguos se borran al generar).
    'retener' => (int) env('RESPALDO_PNNC_RETENER', 30),

    // Binarios (por si no están en el PATH de php-fpm).
    'pg_dump' => env('PG_DUMP_BIN', 'pg_dump'),
    'openssl' => env('OPENSSL_BIN', 'openssl'),

    // Segundos máximos para el pg_dump (la BD ~1.4 GB tarda ~30 s).
    'timeout' => (int) env('RESPALDO_PNNC_TIMEOUT', 600),
];
