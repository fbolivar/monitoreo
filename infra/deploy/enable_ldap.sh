#!/usr/bin/env bash
# Activa y guarda la configuración LDAP. Valores por variables de entorno:
# HOST PORT BINDPAT ROL (no sensibles; no se guardan en el repo).
set -uo pipefail
source /root/monitoreo-secrets.env
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

BODY=$(printf '{"enabled":true,"host":"%s","port":%s,"use_tls":false,"bind_pattern":"%s","rol_default":"%s"}' \
  "$HOST" "$PORT" "$BINDPAT" "${ROL:-viewer}")

echo "Guardando (enabled=true)…"
curl -sk -o /dev/null -w '  PUT -> %{http_code}\n' -X PUT https://127.0.0.1/api/config/ldap \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$BODY"
echo "Config persistida:"
curl -sk https://127.0.0.1/api/config/ldap -H "Authorization: Bearer $TOKEN"; echo
