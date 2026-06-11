#!/usr/bin/env bash
cd /opt/monitoreo/monitor
.venv/bin/python - <<'PY'
import pysnmp
print("pysnmp version:", getattr(pysnmp, "__version__", "?"))
import pysnmp.hlapi.asyncio as m
cmds = [x for x in dir(m) if "cmd" in x.lower()]
print("comandos *cmd*:", cmds)
print("tiene get_cmd:", hasattr(m, "get_cmd"), "| getCmd:", hasattr(m, "getCmd"))
t = m.UdpTransportTarget
print("UdpTransportTarget.create:", hasattr(t, "create"))
import inspect
try:
    print("firma create:", inspect.signature(t.create))
except Exception as e:
    print("no create:", e)
try:
    print("firma __init__:", inspect.signature(t.__init__))
except Exception as e:
    print("init:", e)
PY
