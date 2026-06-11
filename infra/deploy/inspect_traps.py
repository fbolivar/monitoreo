import pysnmp
print("pysnmp", getattr(pysnmp, "__version__", "?"))
from pysnmp.entity import engine, config
print("config.add:", sorted(a for a in dir(config) if "add" in a.lower()))
print("engine attrs:", [a for a in dir(engine.SnmpEngine()) if "disp" in a.lower() or "transport" in a.lower()])
from pysnmp.carrier.asyncio.dgram import udp
print("udp:", [a for a in dir(udp) if not a.startswith("_")])
from pysnmp.entity.rfc3413 import ntfrcv
print("ntfrcv:", [a for a in dir(ntfrcv) if not a.startswith("_")])
ut = udp.UdpTransport()
print("UdpTransport methods:", [a for a in dir(ut) if "server" in a.lower() or "open" in a.lower()])
