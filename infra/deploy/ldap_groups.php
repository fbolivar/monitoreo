<?php
// Lista los grupos (memberOf) de un usuario en AD. Credenciales por entorno:
// LH (host), LU (bind UPN), LP (pass), LB (base DN), LSAM (sAMAccountName a consultar).
@ldap_set_option(null, LDAP_OPT_X_TLS_REQUIRE_CERT, LDAP_OPT_X_TLS_NEVER);
$c = ldap_connect(getenv('LH'));
ldap_set_option($c, LDAP_OPT_PROTOCOL_VERSION, 3);
ldap_set_option($c, LDAP_OPT_REFERRALS, 0);
ldap_set_option($c, LDAP_OPT_NETWORK_TIMEOUT, 8);
if (! @ldap_bind($c, getenv('LU'), getenv('LP'))) {
    fwrite(STDERR, "bind FALLÓ\n");
    exit(1);
}
$sam = getenv('LSAM');
$sr = ldap_search($c, getenv('LB'), "(sAMAccountName=$sam)", ['memberOf', 'displayName']);
$e = ldap_get_entries($c, $sr);
if (empty($e[0])) { echo "usuario no encontrado\n"; exit; }
echo 'Usuario: '.($e[0]['displayname'][0] ?? $sam)."\n";
echo "Grupos (memberOf):\n";
$m = $e[0]['memberof'] ?? [];
unset($m['count']);
sort($m);
foreach ($m as $g) { echo "  $g\n"; }
echo '('.count($m)." grupos)\n";
