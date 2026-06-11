#!/usr/bin/env bash
# Configura el canal Telegram y envía un mensaje de prueba.
# Uso: TG_TOKEN='123:ABC' TG_CHAT='123456789' bash test_telegram.sh
set -euo pipefail
source /root/monitoreo-secrets.env
: "${TG_TOKEN:?Falta TG_TOKEN}"; : "${TG_CHAT:?Falta TG_CHAT}"

echo "== 1) Prueba directa a la API de Telegram =="
RESP=$(curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
  -d chat_id="${TG_CHAT}" \
  --data-urlencode text="✅ SIMON: prueba de canal Telegram. Si ves esto, la integración funciona.")
echo "$RESP" | head -c 300; echo
echo "$RESP" | grep -q '"ok":true' && echo "  -> Telegram OK" || { echo "  -> FALLÓ (revisa token/chat_id)"; exit 1; }

echo "== 2) Crear/activar el canal Telegram en SIMON (vía API) =="
TOKEN=$(curl -sk https://127.0.0.1/api/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" | sed -E 's/.*"token":"([^"]+)".*/\1/')

# ¿Ya existe un canal telegram? (idempotente)
EXIST=$(curl -sk 'https://127.0.0.1/api/canales-notificacion?tipo=telegram' -H "Authorization: Bearer $TOKEN" \
  | sed -E 's/.*"id":([0-9]+).*/\1/;t;d' | head -1)

BODY=$(printf '{"tipo":"telegram","nombre":"Telegram NOC","activo":true,"config":{"chat_id":"%s","min_severidad":"warning"},"secretos":{"bot_token":"%s"}}' "$TG_CHAT" "$TG_TOKEN")

if [ -n "${EXIST:-}" ]; then
  echo "  actualizando canal telegram id=$EXIST"
  curl -sk -o /dev/null -w '  PUT -> %{http_code}\n' -X PUT "https://127.0.0.1/api/canales-notificacion/$EXIST" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$BODY"
else
  echo "  creando canal telegram"
  curl -sk -o /dev/null -w '  POST -> %{http_code}\n' -X POST "https://127.0.0.1/api/canales-notificacion" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$BODY"
fi

echo "== 3) Canales activos =="
curl -sk 'https://127.0.0.1/api/canales-notificacion' -H "Authorization: Bearer $TOKEN" \
  | sed -E 's/\{/\n{/g' | grep -iE '"tipo"|"nombre"|"activo"' | head -20
