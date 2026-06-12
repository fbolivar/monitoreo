#!/usr/bin/env bash
# Descubre subdominios vía Certificate Transparency (certspotter, con fallback crt.sh).
# Uso: DOM=parquesnacionales.gov.co bash descubrir_subdominios.sh
set -uo pipefail
DOM="${DOM:?falta DOM}"
PY=/opt/monitoreo/monitor/.venv/bin/python
UA="Mozilla/5.0 (SIMON-discovery)"

echo "[1] certspotter…"
curl -s --max-time 45 -A "$UA" \
  "https://api.certspotter.com/v1/issuances?domain=${DOM}&include_subdomains=true&expand=dns_names" \
  -o /tmp/cs.json -w "  http=%{http_code} bytes=%{size_download}\n" || true

echo "[2] crt.sh (fallback)…"
curl -s --max-time 45 -A "$UA" "https://crt.sh/?q=%25.${DOM}&output=json" \
  -o /tmp/crt.json -w "  http=%{http_code} bytes=%{size_download}\n" || true

"$PY" - "$DOM" <<'PYEOF'
import json, sys
dom = sys.argv[1]
names = set()
def add(n):
    n = (n or "").strip().lower().rstrip(".")
    if n.endswith(dom) and "*" not in n and n != dom:
        names.add(n)
# certspotter
try:
    for it in json.load(open("/tmp/cs.json")):
        for n in it.get("dns_names", []):
            add(n)
except Exception:
    pass
# crt.sh
try:
    for c in json.load(open("/tmp/crt.json")):
        for n in (c.get("name_value","") or "").split("\n"):
            add(n)
except Exception:
    pass
print(f"\n{len(names)} subdominios únicos de {dom}:")
for n in sorted(names):
    print("  ", n)
PYEOF
