#!/usr/bin/env python3
"""SIMON · Agente ligero (#8) — telemetría "desde dentro" del SO.

Recolecta CPU, memoria, disco por volumen, top procesos y servicios (lo que SNMP
no da) y los envía por HTTPS a SIMON: POST /api/ingest/agente, autenticado con un
token (cabecera X-Agent-Token). Pensado para Windows y Linux.

Instalación (Linux): copiar este archivo + `pip install psutil`; crear un timer
systemd o cron que lo ejecute cada minuto. Windows: Tarea Programada cada 1 min.

Config por entorno:
  SIMON_URL    = https://192.168.50.54   (base de la API)
  SIMON_TOKEN  = <token del agente>       (lo crea un admin en SIMON)
  SIMON_VERIFY = 0 para aceptar el cert autofirmado (por defecto 1)
"""
from __future__ import annotations

import json
import os
import socket
import ssl
import sys
import urllib.request


def recolectar() -> dict:
    import psutil  # dependencia única

    cpu = psutil.cpu_percent(interval=1.0)
    vm = psutil.virtual_memory()
    discos = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
        except (PermissionError, OSError):
            continue
        discos.append({"montaje": p.mountpoint, "pct": u.percent,
                       "total_gb": round(u.total / 1e9, 1), "usado_gb": round(u.used / 1e9, 1)})

    # Top 5 procesos por CPU.
    procs = []
    for pr in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(pr.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top = sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:5]

    servicios = _servicios()

    return {
        "hostname": socket.gethostname(),
        "so": f"{os.name} {sys.platform}",
        "version": "1.0",
        "metricas": {"cpu": cpu, "mem": vm.percent,
                     **{f"disco_{d['montaje']}": d["pct"] for d in discos}},
        "inventario": {"discos": discos, "top_procesos": top, "servicios": servicios,
                       "servicios_vigilados": _servicios_vigilados()},
    }


# Lista vigilada por defecto (Windows / Hyper-V). Se puede sobreescribir por
# entorno con SIMON_SERVICIOS="svc1,svc2,..." (p. ej. en servidores Linux).
# Su ESTADO explícito (running/stopped/absent) habilita políticas de cumplimiento
# en ambos sentidos: "debe estar activo" y "no debe estar corriendo".
WATCH_DEFAULT = [
    "vmms", "vmcompute",                               # Hyper-V (rol del servidor)
    "FCTSvc", "FCT_SecSvr",                            # antivirus/endpoint: FortiClient
    "WinDefend", "MpsSvc",                             # seguridad: Defender, Firewall
    "EventLog", "Schedule", "W32Time",                 # logging, tareas (de él vive el agente), hora
    "LanmanServer", "Dnscache", "RpcSs",               # red / infraestructura
    "TlntSvr", "FTPSVC", "RemoteRegistry", "SSDPSRV",  # inseguros: deberían estar apagados
]


def _servicios_vigilados() -> list[dict]:
    """Estado explícito (running/stopped/absent) de una lista vigilada de servicios."""
    env = os.getenv("SIMON_SERVICIOS", "").strip()
    extra = [n.strip() for n in env.split(",") if n.strip()]
    nombres = list(dict.fromkeys(WATCH_DEFAULT + extra))  # default + extra (env), sin duplicados
    out: list[dict] = []
    try:
        if sys.platform.startswith("win"):
            import psutil
            for n in nombres:
                try:
                    out.append({"nombre": n, "estado": psutil.win_service_get(n).status()})
                except Exception:  # noqa: BLE001  (servicio inexistente)
                    out.append({"nombre": n, "estado": "absent"})
        else:
            import subprocess
            for n in nombres:
                try:
                    r = subprocess.run(["systemctl", "is-active", n],
                                       capture_output=True, text=True, timeout=5)
                    est = (r.stdout or "").strip()
                    out.append({"nombre": n, "estado": "running" if est == "active" else (est or "absent")})
                except Exception:  # noqa: BLE001
                    out.append({"nombre": n, "estado": "absent"})
    except Exception:  # noqa: BLE001
        return []
    return out


def _servicios() -> list[dict]:
    """Servicios (Windows) o unidades systemd (Linux) en estado no-activo."""
    try:
        if sys.platform.startswith("win"):
            import psutil
            return [{"nombre": s.name(), "estado": s.status()}
                    for s in psutil.win_service_iter() if s.status() != "running"][:20]
        import subprocess
        out = subprocess.run(["systemctl", "--failed", "--no-legend", "--plain"],
                             capture_output=True, text=True, timeout=10).stdout
        return [{"nombre": l.split()[0], "estado": "failed"} for l in out.splitlines() if l.strip()][:20]
    except Exception:  # noqa: BLE001
        return []


def enviar(base: str, token: str, verify: bool, payload: dict) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/api/ingest/agente", data=data,
                                 headers={"Content-Type": "application/json", "X-Agent-Token": token})
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        return r.status


def main() -> int:
    base = os.getenv("SIMON_URL", "https://127.0.0.1")
    token = os.getenv("SIMON_TOKEN", "")
    verify = os.getenv("SIMON_VERIFY", "1") not in ("0", "false", "no")
    if not token:
        print("Falta SIMON_TOKEN", file=sys.stderr)
        return 2
    payload = recolectar()
    try:
        code = enviar(base, token, verify, payload)
        print(f"OK ({code}) {payload['hostname']}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"Error enviando: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
