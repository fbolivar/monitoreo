"""Fallback de hardware vía IPMI (BMC legado: iDRAC<9, Supermicro, etc.).

Usa el binario `ipmitool` (debe estar instalado en el worker). El parseo de la
salida es PURO y testeable; la E/S (subprocess) se aísla en `consultar`. Menos
rico que Redfish (sin RAID/inventario detallado), pero universal.
"""
from __future__ import annotations

import subprocess

# Estado IPMI (columna 'status' de `ipmitool sensor`) -> estado interno.
_ESTADO = {"ok": "up", "nc": "degraded", "cr": "down", "nr": "down", "ns": "unknown"}

# Unidad IPMI -> (categoria, unidad normalizada).
_UNIDAD = {
    "degrees c": ("thermal", "°C"),
    "degrees f": ("thermal", "°F"),
    "rpm": ("fan", "RPM"),
    "watts": ("power", "W"),
    "volts": ("power", "V"),
    "amps": ("power", "A"),
}


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_sensor(salida: str) -> list[dict]:
    """Parsea `ipmitool sensor` (campos separados por '|') a componentes."""
    comps: list[dict] = []
    for linea in (salida or "").splitlines():
        if "|" not in linea:
            continue
        campos = [c.strip() for c in linea.split("|")]
        if len(campos) < 4:
            continue
        nombre, valor, unidad, estado = campos[0], campos[1], campos[2], campos[3]
        est = _ESTADO.get(estado.lower())
        if est is None:
            continue
        lectura = _f(valor)
        cat, uni = _UNIDAD.get(unidad.lower(), ("chassis", None))
        # Sensor discreto sin lectura numérica y sin fallo: lo omitimos.
        if lectura is None and est in ("up", "unknown"):
            continue
        comps.append({
            "categoria": cat, "nombre": nombre, "estado": est,
            "lectura": lectura, "unidad": uni if lectura is not None else None,
            "detalle": {},
        })
    return comps


def parse_fru(salida: str) -> dict:
    """Parsea `ipmitool fru` (líneas 'Clave : Valor') al inventario básico."""
    campos: dict[str, str] = {}
    for linea in (salida or "").splitlines():
        if ":" not in linea:
            continue
        k, _, v = linea.partition(":")
        k, v = k.strip(), v.strip()
        if v:
            campos[k] = v
    return {
        "fabricante": campos.get("Product Manufacturer") or campos.get("Board Mfg"),
        "modelo": campos.get("Product Name") or campos.get("Board Product"),
        "serial": campos.get("Product Serial") or campos.get("Board Serial"),
        "sku": campos.get("Product Part Number"),
    }


def salud_global(componentes: list[dict]) -> str:
    """Peor estado entre los componentes (down > degraded > up > unknown)."""
    orden = {"down": 3, "degraded": 2, "up": 1, "unknown": 0}
    if not componentes:
        return "unknown"
    peor = max(componentes, key=lambda c: orden.get(c["estado"], 0))
    return peor["estado"] if orden.get(peor["estado"], 0) > 0 else "unknown"


# ── E/S (subprocess) ────────────────────────────────────────────────────
def consultar(host: str, user: str, password: str, timeout: float) -> dict:
    """Ejecuta ipmitool (sensor + fru) contra el BMC. Lanza si no responde."""
    base = ["ipmitool", "-I", "lanplus", "-H", host, "-U", user, "-P", password]

    def correr(args: list[str]) -> str:
        r = subprocess.run(base + args, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return r.stdout or ""

    sensor = correr(["sensor"])
    if not sensor.strip():
        raise RuntimeError("ipmitool no devolvió sensores (BMC inaccesible o credenciales)")
    fru = correr(["fru"])
    return {"sensor": sensor, "fru": fru}
