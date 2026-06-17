"""Auto-descubrimiento: lógica PURA (sin red ni BD).

- `expandir_subred`: CIDR -> lista de IPs de host (con tope de seguridad).
- `clasificar`: a partir de sysDescr/sysObjectID propone un tipo de recurso.
"""
from __future__ import annotations

import ipaddress

# Número de empresa SNMP (rama 1.3.6.1.4.1.<n>) -> tipo de recurso sugerido.
_ENTERPRISE = {
    "9": "switch_lan",       # Cisco
    "12356": "firewall",     # Fortinet (FortiGate; FortiSwitch se afina por sysDescr)
    "311": "servidor",       # Microsoft (Windows)
    "8072": "servidor",      # net-snmp (Linux/Unix)
    "2021": "servidor",      # UCD-SNMP (Linux)
    "318": "ups",            # APC
    "6574": "nas",           # Synology
    "24681": "nas",          # QNAP
    "674": "switch_lan",     # Dell (redes; servidores Dell se afinan por sysDescr)
}

# Palabras clave en sysDescr (prioritarias sobre el enterprise).
_KEYWORDS = [
    ("fortiswitch", "switch_lan"),
    ("fortigate", "firewall"),
    ("fortinet", "firewall"),
    ("windows", "servidor"),
    ("vmware", "servidor"),
    ("esxi", "servidor"),
    ("linux", "servidor"),
    ("ubuntu", "servidor"),
    ("debian", "servidor"),
    ("centos", "servidor"),
    ("force10", "switch_lan"),
    ("os9", "switch_lan"),
    ("os10", "switch_lan"),
    ("catalyst", "switch_lan"),
    ("cisco ios", "switch_lan"),
    ("switch", "switch_lan"),
    ("synology", "nas"),
    ("qnap", "nas"),
    ("truenas", "nas"),
    ("freenas", "nas"),
    ("apc", "ups"),
    ("ups", "ups"),
]


def expandir_subred(cidr: str, max_hosts: int = 1024) -> list[str]:
    """CIDR (o IP suelta) -> lista de IPs de host. [] si es inválida o excede el tope."""
    cidr = (cidr or "").strip()
    try:
        if "/" not in cidr:
            return [str(ipaddress.ip_address(cidr))]
        red = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return []
    if red.num_addresses > max_hosts + 2:
        return []
    hosts = list(red.hosts()) if red.num_addresses > 2 else list(red)
    return [str(ip) for ip in hosts]


def clasificar(sysdescr: str | None, sysobjectid: str | None) -> str | None:
    """Propone un tipo de recurso (codigo) desde sysDescr/sysObjectID; None si no se sabe."""
    descr = (sysdescr or "").lower()
    for kw, tipo in _KEYWORDS:
        if kw in descr:
            return tipo

    oid = (sysobjectid or "").strip()
    if oid.startswith("1.3.6.1.4.1."):
        ent = oid[len("1.3.6.1.4.1."):].split(".", 1)[0]
        return _ENTERPRISE.get(ent)
    return None
