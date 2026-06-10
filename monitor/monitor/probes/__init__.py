"""Probes disponibles y selección por recurso.

FASE 3 (esta): icmp, http, tcp.
FASE 3b (pendiente): snmp, starlink (gRPC), fortinet (API).
"""
from __future__ import annotations

from ..models import Recurso
from .base import Muestra, Probe, ResultadoProbe
from .fortigate import FortiGateProbe
from .http import HttpProbe
from .icmp import IcmpProbe
from .snmp import SnmpProbe
from .starlink import StarlinkProbe
from .tcp import TcpProbe

__all__ = ["Muestra", "Probe", "ResultadoProbe", "seleccionar_probe"]

# Tipos que se monitorean por SNMP (FASE 3b, paso 1).
_TIPOS_SNMP = {"servidor", "switch_lan", "switch_san", "nas", "ups"}


def seleccionar_probe(recurso: Recurso) -> Probe | None:
    """Elige el probe según el tipo/parámetros del recurso.

    Reglas (orden de precedencia):
      1. Sitios web o URLs http(s)          -> HttpProbe
      2. parametros.metodo == 'tcp'         -> TcpProbe (servicio específico)
      3. parametros.metodo == 'snmp' o tipo -> SnmpProbe (servidor/switch/nas/san/ups)
         en _TIPOS_SNMP
      4. tipo 'starlink'                    -> StarlinkProbe (gRPC, con fallback ICMP)
      5. tipo 'firewall'                    -> FortiGateProbe (API REST, clúster HA)
      6. Cualquier recurso con IP/hostname  -> IcmpProbe (cobertura general)
      7. Sin hostname -> None (no evaluable)
    """
    params = recurso.parametros or {}
    host = (recurso.hostname or "").strip()

    if recurso.tipo_codigo == "sitio_web" or host.startswith(("http://", "https://")):
        return HttpProbe()

    if params.get("metodo") == "tcp" or params.get("check") == "tcp":
        return TcpProbe()

    if params.get("metodo") == "snmp" or recurso.tipo_codigo in _TIPOS_SNMP:
        return SnmpProbe()

    if recurso.tipo_codigo == "starlink" or params.get("metodo") == "starlink":
        return StarlinkProbe()

    if recurso.tipo_codigo == "firewall" or params.get("metodo") == "fortigate":
        return FortiGateProbe()

    if not host:
        return None

    return IcmpProbe()
