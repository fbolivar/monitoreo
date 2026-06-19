"""Probe MPLS por tráfico (vía FortiGate).

Para sedes remotas detrás de la MPLS cuyo gateway NO responde ICMP (router que
enruta el tráfico pero bloquea el ping — confirmado: ni el propio FortiGate lo
alcanza). En vez de pinguear, un job global (`refrescar_trafico_mpls`) consulta
las **sesiones activas** del FortiGate y marca qué subredes de sede tienen
tráfico; este probe lee esa actividad y decide up/down por presencia de tráfico
reciente — la única señal fiable para esos enlaces.

Opt-in por recurso:
    parametros.metodo = 'mpls'
    parametros.subred = '192.168.x.0/27'   (la subred exacta de la sede, de la
                                            tabla de rutas del FortiGate)
"""
from __future__ import annotations

import ipaddress
import re
import threading
import time

from .base import Muestra, ResultadoProbe

# --- Caché compartida en proceso (la actualiza el job, la lee el probe) --------
_LOCK = threading.Lock()
_ULTIMO_ACTIVO: dict[str, float] = {}        # subred -> epoch de la última vez con tráfico
_ULTIMA_ACTUALIZACION: float | None = None   # epoch del último muestreo exitoso

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


# ============================ Lógica pura (testeable) =========================
def extraer_ips(texto: str) -> set[str]:
    """Extrae todas las IPv4 válidas de un volcado de sesiones del FortiGate."""
    out: set[str] = set()
    for m in _IP_RE.finditer(texto or ""):
        ip = m.group(0)
        if all(0 <= int(p) <= 255 for p in ip.split(".")):
            out.add(ip)
    return out


def parsear_subredes(pares: list[tuple[str, int]]) -> dict[str, "ipaddress.IPv4Network"]:
    """[(subred_str, recurso_id)] -> {subred_str: IPv4Network}. Ignora inválidas."""
    res: dict[str, ipaddress.IPv4Network] = {}
    for subred, _rid in pares:
        try:
            res[subred] = ipaddress.ip_network(subred, strict=False)
        except ValueError:
            continue
    return res


def subredes_con_trafico(ips: set[str], subredes: dict[str, "ipaddress.IPv4Network"]) -> dict[str, int]:
    """{subred: nº de IPs activas} para las subredes con al menos una IP activa."""
    ip_objs = []
    for s in ips:
        try:
            ip_objs.append(ipaddress.ip_address(s))
        except ValueError:
            continue
    activos: dict[str, int] = {}
    for nombre, net in subredes.items():
        n = sum(1 for ip in ip_objs if ip in net)
        if n:
            activos[nombre] = n
    return activos


def evaluar_actividad(subred: str | None, ultimo_activo: float | None,
                      ultima_actualizacion: float | None, ahora: float,
                      ventana_seg: int) -> tuple[str, float | None, str]:
    """(estado, edad_seg, motivo) a partir de la caché de actividad. Puro."""
    if not subred:
        return "unknown", None, "recurso MPLS sin 'subred' en parámetros"
    if ultima_actualizacion is None:
        return "unknown", None, "esperando primer muestreo de sesiones del FortiGate"
    if ultimo_activo is None:
        return "down", None, "sin tráfico registrado en la subred"
    edad = ahora - ultimo_activo
    if edad <= ventana_seg:
        return "up", edad, f"tráfico activo hace {int(edad)}s"
    return "down", edad, f"sin tráfico hace {int(edad)}s (> {ventana_seg}s)"


# ============================ Estado de la caché =============================
def actualizar_cache(subredes_activas: dict[str, int], ahora: float) -> None:
    """El job marca las subredes vistas con tráfico y sella el muestreo."""
    global _ULTIMA_ACTUALIZACION
    with _LOCK:
        for subred in subredes_activas:
            _ULTIMO_ACTIVO[subred] = ahora
        _ULTIMA_ACTUALIZACION = ahora


def sembrar_cache(filas: list[tuple[str, float]]) -> None:
    """Carga inicial desde BD: [(subred, epoch)]. NO marca 'actualizado' (eso lo
    hace el primer muestreo en vivo, para no dar up/down con datos viejos)."""
    with _LOCK:
        for subred, epoch in filas:
            _ULTIMO_ACTIVO[subred] = epoch


def _leer_cache(subred: str) -> tuple[float | None, float | None]:
    with _LOCK:
        return _ULTIMO_ACTIVO.get(subred), _ULTIMA_ACTUALIZACION


# ====================== I/O: volcado de sesiones por SSH =====================
def obtener_sesiones(host: str, port: int, user: str, password: str,
                     iface: str, timeout: float) -> str:
    """Vuelca las sesiones de la interfaz MPLS (ambos sentidos) por SSH a FortiOS."""
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=user, password=password,
                   timeout=timeout, look_for_keys=False, allow_agent=False,
                   banner_timeout=timeout, auth_timeout=timeout)
    try:
        shell = client.invoke_shell(width=512, height=2000)
        shell.settimeout(timeout)
        time.sleep(0.6)
        _drenar(shell)
        # Paginador OFF (si no, el volcado sale por páginas con '--More--').
        for linea in ("config system console", "set output standard", "end"):
            shell.send(linea + "\n")
            time.sleep(0.4)
            _drenar(shell)
        # Un volcado por sentido. CLAVE: leer el volcado COMPLETO antes de enviar
        # el siguiente comando; si no, el filtro se entremezcla y no aplica.
        salida = ""
        for direccion in ("dstintf", "srcintf"):
            shell.send("diagnose sys session filter clear\n")
            time.sleep(0.3)
            _drenar(shell)
            shell.send(f"diagnose sys session filter {direccion} {iface}\n")
            time.sleep(0.3)
            _drenar(shell)
            shell.send("diagnose sys session list\n")
            salida += _leer_hasta_inactividad(shell, timeout)
        return salida
    finally:
        client.close()


def _drenar(shell) -> str:
    buf = ""
    while shell.recv_ready():
        buf += shell.recv(65535).decode("utf-8", "ignore")
    return buf


def _leer_hasta_inactividad(shell, timeout: float, quietud: float = 2.0) -> str:
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


# =================================== Probe ===================================
class MplsTraficoProbe:
    nombre = "mpls"
    requiere_secretos = False

    def run(self, recurso, secretos, settings) -> ResultadoProbe:
        params = recurso.parametros or {}
        subred = params.get("subred")
        ahora = time.time()
        ultimo, ultima_act = _leer_cache(subred) if subred else (None, None)
        estado, edad, motivo = evaluar_actividad(
            subred, ultimo, ultima_act, ahora, settings.mpls_actividad_seg)

        detalle = {"subred": subred, "motivo": motivo, "via": "fortigate-trafico"}
        metricas: list[Muestra] = []
        if edad is not None:
            metricas.append(Muestra("trafico_min", round(edad / 60, 1), "min"))
        return ResultadoProbe(estado == "up", estado, None, metricas, detalle)
