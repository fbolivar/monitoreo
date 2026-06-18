"""Probe VMware vCenter (#9) — inventario por-VM vía REST API.

Parsers PUROS + E/S httpx aislada. Usa la API REST de vCenter 7+/8:
  POST /api/session                 -> token de sesión
  GET  /api/vcenter/vm              -> lista de VMs (id, nombre, power_state, cpu, mem)
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def parse_vms(items: list[dict]) -> list[dict]:
    """Normaliza la lista de /api/vcenter/vm (función pura)."""
    out: list[dict] = []
    for v in items or []:
        out.append({
            "vm_id": v.get("vm"),
            "nombre": v.get("name"),
            "power_state": v.get("power_state"),
            "cpu_count": v.get("cpu_count"),
            "memoria_mb": v.get("memory_size_MiB"),
            "guest_os": v.get("guest_OS") or v.get("guest_os"),
        })
    return out


def obtener_inventario(host: str, usuario: str, password: str,
                       verify_tls: bool, timeout: float) -> list[dict]:
    """Consulta vCenter y devuelve el inventario de VMs (I/O)."""
    import httpx

    base = f"https://{host}"
    with httpx.Client(verify=verify_tls, timeout=timeout) as cli:
        r = cli.post(f"{base}/api/session", auth=(usuario, password))
        r.raise_for_status()
        token = r.json() if isinstance(r.json(), str) else r.json().get("value")
        headers = {"vmware-api-session-id": token}
        rv = cli.get(f"{base}/api/vcenter/vm", headers=headers)
        rv.raise_for_status()
        data = rv.json()
        items = data.get("value", data) if isinstance(data, dict) else data
        return parse_vms(items)
