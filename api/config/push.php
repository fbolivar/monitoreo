<?php

// Clave pública VAPID para Web Push (#11). La privada vive en el worker (.env).
return [
    'vapid_public' => env('VAPID_PUBLIC_KEY', ''),
];
