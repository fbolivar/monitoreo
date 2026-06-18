"""Auto-remediación / runbooks (#5).

Al abrir una incidencia, ejecuta acciones automáticas que coincidan con sus
disparadores: un webhook a un orquestador (Rundeck/n8n/Ansible AWX) o un comando
SSH directo al equipo (reiniciar un servicio, rebotar un puerto…).

La coincidencia es PURA y testeable; la ejecución (httpx/paramiko) está aislada.
"""
from __future__ import annotations

import logging

SEV_ORDEN = {"info": 1, "warning": 2, "critical": 3}

log = logging.getLogger(__name__)


def runbook_coincide(rb: dict, ctx: dict) -> bool:
    """¿El runbook aplica a esta incidencia? (función pura).

    rb: trigger_tipo_id, trigger_severidad (mínima), trigger_match (subcadena).
    ctx: tipo_id, severidad, titulo.
    """
    if not rb.get("activo", True):
        return False
    t = rb.get("trigger_tipo_id")
    if t is not None and t != ctx.get("tipo_id"):
        return False
    sev_min = rb.get("trigger_severidad")
    if sev_min and SEV_ORDEN.get(ctx.get("severidad", "info"), 0) < SEV_ORDEN.get(sev_min, 0):
        return False
    match = (rb.get("trigger_match") or "").strip().lower()
    if match and match not in (ctx.get("titulo") or "").lower():
        return False
    return True


def interpolar(texto: str, ctx: dict) -> str:
    """Sustituye {recurso}/{hostname}/{titulo}/{severidad} en comandos/URLs."""
    for k in ("recurso", "hostname", "titulo", "severidad", "incidencia_id"):
        texto = texto.replace("{" + k + "}", str(ctx.get(k, "")))
    return texto


def ejecutar_accion(accion: dict, ctx: dict, secretos: dict | None) -> tuple[bool, str]:
    """Ejecuta la acción del runbook. Devuelve (exito, salida)."""
    secretos = secretos or {}
    tipo = (accion or {}).get("tipo")
    if tipo == "webhook":
        return _webhook(accion, ctx, secretos)
    if tipo == "ssh":
        return _ssh(accion, ctx, secretos)
    return False, f"tipo de acción no soportado: {tipo}"


def _webhook(accion: dict, ctx: dict, secretos: dict) -> tuple[bool, str]:
    import httpx

    url = interpolar(accion.get("url", ""), ctx)
    if not url:
        return False, "webhook sin url"
    headers = {}
    if secretos.get("token"):
        headers["Authorization"] = f"Bearer {secretos['token']}"
    payload = accion.get("payload") or {
        "recurso": ctx.get("recurso"), "hostname": ctx.get("hostname"),
        "titulo": ctx.get("titulo"), "severidad": ctx.get("severidad"),
        "incidencia_id": ctx.get("incidencia_id"),
    }
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        return True, f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _ssh(accion: dict, ctx: dict, secretos: dict) -> tuple[bool, str]:
    import paramiko

    host = accion.get("host") or ctx.get("hostname")
    comando = interpolar(accion.get("comando", ""), ctx)
    if not host or not comando:
        return False, "ssh sin host/comando"
    usuario = secretos.get("ssh_user") or accion.get("ssh_user")
    if not usuario:
        return False, "ssh sin usuario"

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        kwargs: dict = {"username": usuario, "timeout": 20, "look_for_keys": False, "allow_agent": False}
        if secretos.get("ssh_key"):
            from io import StringIO
            kwargs["pkey"] = paramiko.RSAKey.from_private_key(StringIO(secretos["ssh_key"]))
        else:
            kwargs["password"] = secretos.get("ssh_password", "")
        cli.connect(host.split(":", 1)[0], port=int(accion.get("puerto", 22)), **kwargs)
        _in, out, err = cli.exec_command(comando, timeout=25)
        salida = out.read().decode("utf-8", "replace")[:2000]
        error = err.read().decode("utf-8", "replace")[:500]
        return True, (salida or error or "ok")
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    finally:
        cli.close()
