#!/usr/bin/env bash
# FASE 6 · Paso Frontend: Node 20 + npm ci + ng build. La SPA la sirve nginx.
set -euo pipefail

FE=/opt/monitoreo/frontend
export DEBIAN_FRONTEND=noninteractive

echo "== Node 20 LTS =="
NEED=1
if command -v node >/dev/null; then
  MAJ=$(node -v | sed 's/v//' | cut -d. -f1)
  [ "$MAJ" -ge 20 ] && NEED=0
fi
if [ "$NEED" -eq 1 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
  apt-get install -y -qq nodejs >/dev/null
fi
echo "node $(node -v) / npm $(npm -v)"

echo "== environment.ts: apiUrl -> /api (mismo origen) =="
sed -i "s|apiUrl:.*|apiUrl: '/api',|" "$FE/src/environments/environment.ts"
grep -E "apiUrl|supabaseUrl|supabaseAnonKey" "$FE/src/environments/environment.ts"

echo "== npm ci =="
cd "$FE"
npm ci --no-audit --no-fund 2>&1 | tail -4

echo "== ng build =="
npx ng build --configuration production 2>&1 | tail -10

echo "== artefacto =="
ls -la "$FE/dist/frontend/browser" | head -8

systemctl reload nginx
echo "== verificación HTTP =="
curl -s -o /dev/null -w 'GET /            -> %{http_code}\n' http://127.0.0.1/
echo -n "title: "; curl -s http://127.0.0.1/ | grep -o '<title>[^<]*</title>' || echo "(sin title)"
curl -s -o /dev/null -w 'GET /dashboard   -> %{http_code} (SPA fallback)\n' http://127.0.0.1/dashboard
curl -s -o /dev/null -w 'GET /api/me       -> %{http_code} (API sigue viva)\n' http://127.0.0.1/api/me
