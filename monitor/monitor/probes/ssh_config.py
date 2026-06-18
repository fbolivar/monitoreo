"""Respaldo de configuración de switches por SSH.

Se conecta al switch, deshabilita la paginación y ejecuta el comando de volcado
(p.ej. `show running-configuration`), devolviendo la config como texto. El
comando por defecto y la limpieza de la salida son PUROS/testeables; la E/S
(paramiko, shell interactivo) se aísla en `obtener_config`.
"""
from __future__ import annotations

# Comando de volcado por familia de equipo (heurística por vendor/tipo).
# Dell OS9/OS10 (FTOS), Cisco IOS y Arista EOS aceptan 'show running-config'
# (verificado en Dell OS 9.14: 'show running-configuration' da "Invalid input").
_COMANDOS = {
    "dell_os9": "show running-config",
    "dell_os10": "show running-config",
    "force10": "show running-config",
    "dell": "show running-config",
    "cisco": "show running-config",
    "ios": "show running-config",
    "fortiswitch": "show full-configuration",
    "arista": "show running-config",
}

# Comando para deshabilitar la paginación por familia.
_SIN_PAGINACION = {
    "dell_os9": "terminal length 0",
    "dell_os10": "terminal length 0",
    "force10": "terminal length 0",
    "dell": "terminal length 0",
    "cisco": "terminal length 0",
    "ios": "terminal length 0",
    "arista": "terminal length 0",
    # FortiOS/FortiSwitch: desactiva el paginador con la consola en modo 'standard'
    # (varios comandos; obtener_config los envía línea a línea).
    "fortiswitch": "config system console\nset output standard\nend",
}


def _backup_cfg(parametros: dict) -> dict:
    b = (parametros or {}).get("backup")
    return b if isinstance(b, dict) else {}


def comando_backup(parametros: dict, tipo_codigo: str | None = None) -> str:
    """Comando de volcado: explícito en parametros.backup.comando, o por vendor/tipo."""
    cfg = _backup_cfg(parametros)
    if cfg.get("comando"):
        return str(cfg["comando"])
    vendor = (cfg.get("vendor") or tipo_codigo or "").lower()
    return _COMANDOS.get(vendor, "show running-config")


def comando_sin_paginacion(parametros: dict) -> str:
    """Comando para desactivar el paginador (configurable; def 'terminal length 0')."""
    cfg = _backup_cfg(parametros)
    if "sin_paginacion" in cfg:
        return str(cfg["sin_paginacion"] or "")
    vendor = (cfg.get("vendor") or "").lower()
    return _SIN_PAGINACION.get(vendor, "terminal length 0")


def limpiar_salida(texto: str, comando: str) -> str:
    """Quita el eco del comando, los artefactos del paginador y el prompt final."""
    lineas = (texto or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    limpio: list[str] = []
    for ln in lineas:
        s = ln.rstrip()
        # Artefactos del paginador ('--More--', a veces con secuencias de borrado).
        if "--More--" in s or "<--- More --->" in s:
            continue
        # Eco del comando enviado.
        if s.strip() in (comando.strip(), "terminal length 0"):
            continue
        limpio.append(s)
    # Quita líneas vacías al inicio/fin y un prompt final tipo 'switch#'/'switch>'.
    while limpio and not limpio[0].strip():
        limpio.pop(0)
    while limpio and not limpio[-1].strip():
        limpio.pop()
    if limpio and _es_prompt(limpio[-1]):
        limpio.pop()
    while limpio and not limpio[-1].strip():
        limpio.pop()
    return "\n".join(limpio)


def _es_prompt(linea: str) -> bool:
    """Línea de prompt CLI: corta, NO indentada y terminada en #, > o $.
    Cubre 'switch#' (Dell/Cisco) y 'NOMBRE # ' (FortiOS). Las líneas de config
    van indentadas, así que el filtro por indentación evita falsos positivos."""
    if linea[:1] in (" ", "\t"):
        return False
    s = linea.strip()
    return bool(s) and len(s) < 60 and s[-1] in "#>$"


# ── E/S (paramiko) ──────────────────────────────────────────────────────
def obtener_config(host: str, port: int, user: str, password: str | None,
                   key_pem: str | None, comando: str, sin_paginacion: str,
                   timeout: float) -> str:
    """Conecta por SSH, desactiva paginación y devuelve la salida del comando."""
    import time
    from io import StringIO

    import paramiko

    pkey = None
    if key_pem:
        for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                pkey = cls.from_private_key(StringIO(key_pem))
                break
            except Exception:  # noqa: BLE001
                continue

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=user, password=password, pkey=pkey,
                   timeout=timeout, look_for_keys=False, allow_agent=False,
                   banner_timeout=timeout, auth_timeout=timeout)
    try:
        shell = client.invoke_shell(width=512, height=1000)
        shell.settimeout(timeout)
        time.sleep(0.6)
        _drenar(shell)
        # sin_paginacion puede ser varios comandos (FortiOS): se envían uno a uno.
        for linea in (sin_paginacion or "").split("\n"):
            if linea.strip():
                shell.send(linea + "\n")
                time.sleep(0.4)
                _drenar(shell)
        # `comando` puede ser multilínea (p.ej. la secuencia de config para
        # rebotar un puerto): se envía línea a línea.
        for linea in comando.split("\n"):
            shell.send(linea + "\n")
            time.sleep(0.3)
        salida = _leer_hasta_inactividad(shell, timeout)
    finally:
        client.close()
    return salida


def _drenar(shell) -> str:
    buf = ""
    while shell.recv_ready():
        buf += shell.recv(65535).decode("utf-8", "ignore")
    return buf


def _leer_hasta_inactividad(shell, timeout: float, quietud: float = 1.5) -> str:
    import time

    salida = ""
    inicio = time.perf_counter()
    ultimo = inicio
    while True:
        if shell.recv_ready():
            salida += shell.recv(65535).decode("utf-8", "ignore")
            ultimo = time.perf_counter()
        else:
            time.sleep(0.2)
            if time.perf_counter() - ultimo >= quietud:
                break
        if time.perf_counter() - inicio >= timeout:
            break
    return salida
