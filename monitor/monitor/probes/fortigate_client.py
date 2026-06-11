"""Cliente REST de FortiGate (parte aislada / dependiente de httpx + la API).

Autenticación por token de API (Authorization: Bearer <api_key>). Los firewalls
suelen usar certificado autofirmado, por eso `verify_ssl` es configurable.
"""
from __future__ import annotations


def consultar(host: str, token: str, verify_ssl: bool, timeout: float) -> dict:
    """Consulta uso de recursos y estadísticas HA. Devuelve {'uso':..., 'ha':...}.

    `ha` puede ser None si el equipo no está en clúster (endpoint no disponible).
    Lanza excepción si falla la consulta de uso (equipo inaccesible).
    """
    import httpx

    base = host if host.startswith(("http://", "https://")) else f"https://{host}"
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=base, headers=headers, verify=verify_ssl, timeout=timeout) as c:
        uso_resp = c.get("/api/v2/monitor/system/resource/usage")
        uso_resp.raise_for_status()
        uso = uso_resp.json()

        ha = None
        try:
            ha_resp = c.get("/api/v2/monitor/system/ha-statistics")
            ha_resp.raise_for_status()
            ha = ha_resp.json()
        except Exception:
            ha = None  # equipo standalone o endpoint no disponible

    return {"uso": uso, "ha": ha}


def respaldar_config(host: str, token: str, verify_ssl: bool, timeout: float) -> str:
    """Descarga la configuración completa del FortiGate (texto). Lanza si falla."""
    import httpx

    base = host if host.startswith(("http://", "https://")) else f"https://{host}"
    headers = {"Authorization": f"Bearer {token}"}
    # FortiOS expone el backup como POST (GET devuelve 405).
    with httpx.Client(base_url=base, headers=headers, verify=verify_ssl, timeout=timeout) as c:
        r = c.post("/api/v2/monitor/system/config/backup", params={"scope": "global"})
        r.raise_for_status()
        return r.text

