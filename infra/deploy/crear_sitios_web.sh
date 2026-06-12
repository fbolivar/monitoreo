#!/usr/bin/env bash
# Crea sitios web (subdominios) descubiertos, probando HTTP. Excluye test-/dev-/build.
# Env: U/PASS (admin). Usa /tmp/cs.json (de descubrir_subdominios.sh).
set -uo pipefail
source /root/monitoreo-secrets.env
export PGPASSWORD="$DB_PASSWORD"
A="https://127.0.0.1/api"
P="psql -h 127.0.0.1 -U monitoreo -d monitoreo"
Pt="$P -tAc"
PY=/opt/monitoreo/monitor/.venv/bin/python

T=$(curl -sk "$A/auth/login" -H 'Content-Type: application/json' \
  -d "$(printf '{"email":"%s","password":"%s"}' "${U:-}" "${PASS:-}")" | sed -E 's/.*"token":"([^"]+)".*/\1/')
TIPO=$($Pt "SELECT id FROM tipos_recurso WHERE codigo='sitio_web' LIMIT 1")
SITIO=$($Pt "SELECT id FROM sitios WHERE nombre ILIKE '%Nivel Central%' LIMIT 1"); [ -z "$SITIO" ] && SITIO=null
echo "tipo sitio_web=$TIPO  sitio=$SITIO"

SUBS=$("$PY" - <<'PYEOF'
import json
dom="parquesnacionales.gov.co"; n=set()
try:
    for it in json.load(open("/tmp/cs.json")):
        for x in it.get("dns_names",[]):
            x=x.strip().lower().rstrip(".")
            if x.endswith(dom) and "*" not in x and x!=dom:
                lab=x.split(".")[0]
                if lab.startswith(("test-","dev-")) or lab in ("components","angle-template"):
                    continue
                n.add(x)
except Exception: pass
print("\n".join(sorted(n)))
PYEOF
)

for s in $SUBS; do
  url="https://$s"
  if [ -n "$($Pt "SELECT 1 FROM recursos WHERE hostname='$url' LIMIT 1")" ]; then
    echo "  $s: ya existe"; continue
  fi
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 "$url" 2>/dev/null || echo 000)
  body=$(printf '{"tipo_id":%s,"sitio_id":%s,"nombre":"%s","hostname":"%s","intervalo_segundos":120,"activo":true,"parametros":{}}' \
    "$TIPO" "$SITIO" "$s" "$url")
  curl -sk -o /dev/null -X POST "$A/recursos" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "$body"
  RID=$($Pt "SELECT id FROM recursos WHERE hostname='$url' ORDER BY id DESC LIMIT 1")
  if [ "$code" = "000" ]; then
    $P -c "UPDATE recursos SET activo=false WHERE id=$RID" >/dev/null
    echo "  $s: SIN RESPUESTA -> creado en PAUSA"
  else
    echo "  $s: HTTP $code -> creado ACTIVO"
  fi
done
