"""Probe de hardware físico vía Redfish (DMTF, REST/HTTPS sobre el BMC).

Soporta iDRAC 9+, HPE iLO 5+, Lenovo XClarity, Supermicro X11+, etc. El parseo
es PURO y testeable (recibe los JSON de Redfish); la E/S (httpx + Basic Auth) se
aísla en `consultar`. NO instrumenta el SO del servidor: habla con el controlador
de gestión fuera de banda (out-of-band).
"""
from __future__ import annotations

# Health de Redfish (Status.Health) -> estado interno.
_HEALTH = {"OK": "up", "Warning": "degraded", "Critical": "down"}


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def estado_de(status: dict | None) -> str:
    """Mapea un objeto Redfish Status {Health, State} a up/degraded/down/unknown."""
    if not status:
        return "unknown"
    state = status.get("State")
    if state in ("Absent", "Disabled", "StandbyOffline", "UnavailableOffline"):
        # No presente / fuera de línea: no es un fallo, es ausencia de dato.
        return "unknown"
    return _HEALTH.get(status.get("Health"), "unknown")


def parse_system(sys_json: dict | None) -> dict:
    """Inventario + salud global del sistema (endpoint /Systems/{id})."""
    s = sys_json or {}
    proc = s.get("ProcessorSummary", {}) or {}
    mem = s.get("MemorySummary", {}) or {}
    return {
        "fabricante": s.get("Manufacturer"),
        "modelo": s.get("Model"),
        "serial": s.get("SerialNumber"),
        "sku": s.get("SKU"),
        "bios_version": s.get("BiosVersion"),
        "cpu_modelo": proc.get("Model"),
        "cpu_cantidad": proc.get("Count"),
        "memoria_gb": _f(mem.get("TotalSystemMemoryGiB")),
        "power_state": s.get("PowerState"),
        "salud_global": estado_de(s.get("Status")),
        "host_name": s.get("HostName"),
    }


def parse_thermal(thermal_json: dict | None) -> list[dict]:
    """Temperaturas y ventiladores (endpoint /Chassis/{id}/Thermal)."""
    t = thermal_json or {}
    comps: list[dict] = []

    for s in t.get("Temperatures", []) or []:
        nombre = s.get("Name") or "Temp"
        lectura = _f(s.get("ReadingCelsius"))
        if lectura is None and estado_de(s.get("Status")) == "unknown":
            continue  # sensor ausente sin lectura
        comps.append({
            "categoria": "thermal", "nombre": nombre, "estado": estado_de(s.get("Status")),
            "lectura": lectura, "unidad": "°C",
            "detalle": _limpio({
                "critico": s.get("UpperThresholdCritical"),
                "no_critico": s.get("UpperThresholdNonCritical"),
            }),
        })

    for f in t.get("Fans", []) or []:
        nombre = f.get("Name") or f.get("FanName") or "Fan"
        lectura = _f(f.get("Reading"))
        unidad = f.get("ReadingUnits") or "RPM"
        if lectura is None and estado_de(f.get("Status")) == "unknown":
            continue
        comps.append({
            "categoria": "fan", "nombre": nombre, "estado": estado_de(f.get("Status")),
            "lectura": lectura, "unidad": unidad, "detalle": {},
        })

    return comps


def parse_power(power_json: dict | None) -> list[dict]:
    """Fuentes de poder y consumo (endpoint /Chassis/{id}/Power)."""
    p = power_json or {}
    comps: list[dict] = []

    for ps in p.get("PowerSupplies", []) or []:
        nombre = ps.get("Name") or "PSU"
        comps.append({
            "categoria": "power", "nombre": nombre, "estado": estado_de(ps.get("Status")),
            "lectura": _f(ps.get("PowerInputWatts") or ps.get("LastPowerOutputWatts")),
            "unidad": "W",
            "detalle": _limpio({
                "modelo": ps.get("Model"), "serial": ps.get("SerialNumber"),
                "capacidad_w": ps.get("PowerCapacityWatts"),
                "fabricante": ps.get("Manufacturer"),
            }),
        })

    # Consumo total del chasis (PowerControl).
    for pc in p.get("PowerControl", []) or []:
        watts = _f(pc.get("PowerConsumedWatts"))
        if watts is None:
            continue
        comps.append({
            "categoria": "chassis", "nombre": pc.get("Name") or "Consumo total",
            "estado": "up", "lectura": watts, "unidad": "W",
            "detalle": _limpio({"limite_w": (pc.get("PowerLimit") or {}).get("LimitInWatts")}),
        })

    return comps


def _dicts(valor) -> list[dict]:
    """Solo dicts de una lista. Redfish a veces da una REFERENCIA ({@odata.id})
    en vez de una colección inline (p.ej. Volumes en iDRAC); eso se descarta."""
    if not isinstance(valor, list):
        return []
    return [x for x in valor if isinstance(x, dict)]


def parse_storage(storage_members: list | None) -> list[dict]:
    """Controladores RAID, discos y volúmenes (endpoints /Systems/{id}/Storage/*)."""
    comps: list[dict] = []
    for st in _dicts(storage_members):
        for ctrl in _dicts(st.get("StorageControllers")):
            nombre = ctrl.get("Name") or "Controladora"
            comps.append({
                "categoria": "storage", "nombre": f"Ctrl {nombre}",
                "estado": estado_de(ctrl.get("Status")), "lectura": None, "unidad": None,
                "detalle": _limpio({"modelo": ctrl.get("Model"),
                                    "firmware": ctrl.get("FirmwareVersion")}),
            })
        for d in _dicts(st.get("Drives")):
            nombre = d.get("Name") or d.get("Id") or "Disco"
            cap = d.get("CapacityBytes")
            comps.append({
                "categoria": "storage", "nombre": nombre, "estado": estado_de(d.get("Status")),
                "lectura": round(cap / 1e9, 1) if isinstance(cap, (int, float)) else None,
                "unidad": "GB" if cap else None,
                "detalle": _limpio({"modelo": d.get("Model"), "serial": d.get("SerialNumber"),
                                    "tipo": d.get("MediaType"), "protocolo": d.get("Protocol")}),
            })
        for v in _dicts(st.get("Volumes")):
            nombre = v.get("Name") or v.get("Id") or "Volumen"
            comps.append({
                "categoria": "storage", "nombre": f"Vol {nombre}",
                "estado": estado_de(v.get("Status")), "lectura": None, "unidad": None,
                "detalle": _limpio({"raid": v.get("RAIDType") or v.get("VolumeType")}),
            })
    return comps


def _limpio(d: dict) -> dict:
    """Quita claves con valor None para no ensuciar el jsonb."""
    return {k: v for k, v in d.items() if v is not None}


# ── E/S (httpx) ────────────────────────────────────────────────────────
def consultar(host: str, user: str, password: str, verify_tls: bool, timeout: float) -> dict:
    """Recorre el árbol Redfish del BMC y devuelve los JSON crudos relevantes.

    Estructura devuelta: {system, thermal, power, storage:[...], bmc_firmware}.
    Lanza excepción si no se alcanza el sistema (equipo/BMC inaccesible).
    """
    import httpx

    base = host if host.startswith(("http://", "https://")) else f"https://{host}"

    with httpx.Client(base_url=base, auth=(user, password), verify=verify_tls,
                      timeout=timeout, headers={"Accept": "application/json"}) as c:
        def get(path):
            r = c.get(path)
            r.raise_for_status()
            return r.json()

        def primero(coleccion_path):
            col = get(coleccion_path)
            miembros = col.get("Members", []) or []
            return miembros[0]["@odata.id"] if miembros else None

        root = get("/redfish/v1/")
        sys_path = (root.get("Systems") or {}).get("@odata.id", "/redfish/v1/Systems")
        chas_path = (root.get("Chassis") or {}).get("@odata.id", "/redfish/v1/Chassis")
        mgr_path = (root.get("Managers") or {}).get("@odata.id", "/redfish/v1/Managers")

        system_id = primero(sys_path)
        system = get(system_id) if system_id else {}

        # Almacenamiento (controladoras + discos + volúmenes).
        storage: list = []
        stor_link = (system.get("Storage") or {}).get("@odata.id")
        if stor_link:
            for m in (get(stor_link).get("Members", []) or [])[:8]:
                try:
                    st = get(m["@odata.id"])
                    # Expande discos referenciados (lista de {@odata.id}).
                    drives = []
                    for dref in st.get("Drives", []) or []:
                        if isinstance(dref, dict) and dref.get("@odata.id"):
                            try:
                                drives.append(get(dref["@odata.id"]))
                            except Exception:
                                pass
                    st["Drives"] = drives
                    # Expande volúmenes (Volumes suele ser una REFERENCIA a una colección).
                    volumes = []
                    vlink = (st.get("Volumes") or {})
                    vlink = vlink.get("@odata.id") if isinstance(vlink, dict) else None
                    if vlink:
                        try:
                            for vref in get(vlink).get("Members", []) or []:
                                if isinstance(vref, dict) and vref.get("@odata.id"):
                                    volumes.append(get(vref["@odata.id"]))
                        except Exception:
                            pass
                    st["Volumes"] = volumes
                    storage.append(st)
                except Exception:
                    pass

        # Térmico y energía (del primer chasis).
        thermal = power = {}
        chas_id = _safe(primero, chas_path)
        if chas_id:
            chas = _safe(get, chas_id) or {}
            tlink = (chas.get("Thermal") or {}).get("@odata.id")
            plink = (chas.get("Power") or {}).get("@odata.id")
            if tlink:
                thermal = _safe(get, tlink) or {}
            if plink:
                power = _safe(get, plink) or {}

        # Firmware del BMC.
        bmc_fw = None
        mgr_id = _safe(primero, mgr_path)
        if mgr_id:
            mgr = _safe(get, mgr_id) or {}
            bmc_fw = mgr.get("FirmwareVersion")

    return {"system": system, "thermal": thermal, "power": power,
            "storage": storage, "bmc_firmware": bmc_fw}


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:  # noqa: BLE001
        return None
