<?php

// SSO contra Active Directory / LDAP. Desactivado por defecto: la app sigue
// funcionando con auth local. Para activar, define estas variables en api/.env.
return [
    'enabled'      => env('AUTH_LDAP_ENABLED', false),
    'host'         => env('AUTH_LDAP_HOST'),
    'port'         => (int) env('AUTH_LDAP_PORT', 389),
    'use_tls'      => env('AUTH_LDAP_TLS', false),
    // Patrón para construir el identificador de bind a partir de lo que escribe
    // el usuario. {user} se reemplaza por el valor del campo "correo".
    // Ej. AD por UPN: '{user}'  ·  por dominio: '{user}@parques.gov.co'
    'bind_pattern' => env('AUTH_LDAP_BIND_PATTERN', '{user}'),
    // Rol asignado a un usuario LDAP nuevo (la primera vez que entra).
    'rol_default'  => env('AUTH_LDAP_ROL_DEFAULT', 'viewer'),
    // Restringir el acceso a los miembros de este grupo de AD (DN completo).
    // Vacío = cualquier usuario válido del directorio.
    'group_dn'     => env('AUTH_LDAP_GROUP_DN', ''),
    // Si es false, NO se crean perfiles automáticamente: solo entran los usuarios
    // que un administrador ya creó en SIMON (lista blanca manual).
    'auto_create'  => env('AUTH_LDAP_AUTOCREATE', true),
];
