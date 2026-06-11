"""Cambia el flag NAT de una política FortiGate. Env: FORTI_TOKEN POLICY NAT(enable|disable)."""
import json, os, ssl, urllib.request

token = os.environ["FORTI_TOKEN"]
pid = os.environ["POLICY"]
nat = os.environ["NAT"]
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
base = f"https://192.168.50.1:25443/api/v2/cmdb/firewall/policy/{pid}"
hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

req = urllib.request.Request(base, data=json.dumps({"nat": nat}).encode(), method="PUT", headers=hdr)
r = json.load(urllib.request.urlopen(req, context=ctx, timeout=10))
print("PUT ->", r.get("http_status"), r.get("status"))

v = json.load(urllib.request.urlopen(
    urllib.request.Request(base, headers=hdr), context=ctx, timeout=10))["results"][0]
print(f"policy {pid} '{v.get('name')}' nat={v.get('nat')}")
