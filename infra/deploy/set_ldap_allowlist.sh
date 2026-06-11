#!/usr/bin/env bash
# Activa la lista blanca LDAP y la verifica. Env: U/PASS (admin LDAP en la lista),
# LIST (usuarios permitidos), UNEG/PNEG (usuario válido de AD que NO está en la lista).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
A="https://127.0.0.1/api"
login() { curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "$1" "$2")"; }

T=$(login "$U" "$PASS" | sed -E 's/.*"token":"([^"]+)".*/\1/')

BODY=$(printf '{"enabled":true,"host":"ldaps://192.168.50.2","port":636,"use_tls":false,"bind_pattern":"{user}@pnnc.local","rol_default":"viewer","group_dn":"","auto_create":true,"usuarios_permitidos":"%s"}' "$LIST")
echo -n "PUT lista blanca -> "
curl -sk -o /dev/null -w '%{http_code}\n' -X PUT "$A/config/ldap" -H "Authorization: Bearer $T" \
  -H 'Content-Type: application/json' -d "$BODY"
echo -n "usuarios_permitidos guardado: "
curl -sk "$A/config/ldap" -H "Authorization: Bearer $T" | sed -E 's/.*("usuarios_permitidos":"[^"]*").*/\1/'

echo -n "1) Login de '$U' (EN la lista) -> "
login "$U" "$PASS" | grep -q '"token"' && echo "OK (permitido)" || echo "FALLÓ"

echo -n "2) Login de '$UNEG' (NO en la lista) -> "
R=$(login "$UNEG" "$PNEG")
echo "$R" | grep -q '"token"' && echo "ENTRÓ (mal)" || echo "rechazado (correcto): $(echo "$R" | head -c 60)"
echo -n "   ¿se creó perfil de '$UNEG'? "
psql -h 127.0.0.1 -U monitoreo -d monitoreo -tAc "SELECT count(*) FROM perfiles WHERE email='$UNEG'"
