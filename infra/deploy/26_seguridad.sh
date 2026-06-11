#!/usr/bin/env bash
# Endurecimiento: bloqueo por fuerza bruta + política de contraseñas + idle (frontend).
# Despliega y verifica. Env: U/PASS (admin para la API).
set -uo pipefail
source /root/monitoreo-secrets.env
A="https://127.0.0.1/api"

cd /opt/monitoreo
git checkout -- frontend/src/environments/environment.ts api/composer.json 2>/dev/null || true
git pull --ff-only origin main
git log --oneline -1

( cd api && php artisan optimize:clear >/dev/null 2>&1 || true )
systemctl reload php8.2-fpm 2>/dev/null || true
( cd frontend && npx ng build --configuration production 2>&1 | tail -3 )
systemctl reload nginx

echo "== Política de contraseñas (crear usuario con clave débil -> 422) =="
T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "${U:-}" "${PASS:-}")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
curl -sk -o /dev/null -w '  password débil -> %{http_code} (esperado 422)\n' -X POST "$A/usuarios" \
  -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"email":"zz.pol@test.local","nombre":"x","rol":"viewer","activo":true,"password":"debil123"}'

echo "== Bloqueo por fuerza bruta (usuario falso, 6 intentos) =="
for i in 1 2 3 4 5 6; do
  C=$(curl -sk -o /dev/null -w '%{http_code}' "$A/auth/login" -H 'Content-Type: application/json' \
    -d '{"email":"ataque@test.local","password":"x"}')
  echo "  intento $i -> $C"
done
echo "  (los primeros 5 = 401; el 6º debe ser 429 = bloqueado)"
