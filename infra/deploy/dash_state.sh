#!/usr/bin/env bash
source /root/monitoreo-secrets.env
API=https://127.0.0.1
TOKEN=$(curl -sk -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"admin@entidad.gov.co\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
H="Authorization: Bearer $TOKEN"
curl -sk "$API/api/recursos?per_page=200" -H "$H" -o /tmp/recursos.json
python3 - /tmp/recursos.json <<'PY'
import sys, json
from collections import Counter
d = json.load(open(sys.argv[1]))["data"]
c = Counter(x["estado_actual"] for x in d)
print("RESUMEN (semaforo):", dict(c), "| total:", len(d))
print()
por = {}
for x in d:
    s = (x.get("sitio") or {}).get("nombre", "Sin sitio")
    t = (x.get("tipo") or {}).get("nombre", "Otro")
    por.setdefault(s, {}).setdefault(t, []).append(x)
for sitio, tipos in por.items():
    print(f"== {sitio} ==")
    for tipo, items in tipos.items():
        print(f"  [{tipo}]")
        for x in items:
            print(f"     {x['estado_actual']:9} {x['nombre']:20} {x.get('hostname','') or ''}")
PY
