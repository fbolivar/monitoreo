"""Lista las políticas FortiGate hacia la zona de servidores (orden de evaluación).
Uso: FORTI_TOKEN=... python forti_policies.py"""
import json, os, ssl, urllib.request

token = os.environ["FORTI_TOKEN"]
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(path):
    req = urllib.request.Request(
        f"https://192.168.50.1:25443/api/v2/{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return json.load(urllib.request.urlopen(req, context=ctx, timeout=10))


d = get("cmdb/firewall/policy")
print("politicas hacia SERVIDORES (en orden):")
for p in d.get("results", []):
    di = [x["name"] for x in p.get("dstintf", [])]
    da = [x["name"] for x in p.get("dstaddr", [])]
    if any("SERVIDOR" in n.upper() for n in di + da):
        si = "/".join(x["name"] for x in p.get("srcintf", []))
        sa = "/".join(x["name"] for x in p.get("srcaddr", []))
        print(f"  id={p.get('policyid')} seq nat={p.get('nat')} act={p.get('action')} "
              f"| src: {si} {sa} -> dst: {'/'.join(di)} {'/'.join(da)}")
