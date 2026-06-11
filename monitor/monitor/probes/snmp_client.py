"""Cliente SNMP aislado (la ÚNICA parte dependiente de pysnmp y de su versión).

Soporta SNMP v1/v2c (community) y v3 (USM: noAuth/authNoPriv/authPriv), con GET
y WALK. Compatible con pysnmp 6.x (getCmd/walkCmd, UdpTransportTarget()) y
7.x (get_cmd/walk_cmd, UdpTransportTarget.create()).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class Credenciales:
    version: str                 # '1' | '2c' | '3'
    community: str | None = None
    user: str | None = None
    auth_key: str | None = None
    priv_key: str | None = None
    auth_proto: str = "SHA"      # MD5 | SHA
    priv_proto: str = "AES"      # DES | AES

    def nivel_seguridad(self) -> str:
        if self.version != "3":
            return "n/a"
        if self.auth_key and self.priv_key:
            return "authPriv"
        if self.auth_key:
            return "authNoPriv"
        return "noAuthNoPriv"


def _construir_auth(cred: Credenciales):
    """Devuelve el objeto de autenticación pysnmp (CommunityData/UsmUserData)."""
    from pysnmp.hlapi.asyncio import (
        CommunityData, UsmUserData,
        usmAesCfb128Protocol, usmDESPrivProtocol,
        usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
    )
    auth_protos = {"MD5": usmHMACMD5AuthProtocol, "SHA": usmHMACSHAAuthProtocol}
    priv_protos = {"DES": usmDESPrivProtocol, "AES": usmAesCfb128Protocol}

    if cred.version in ("1", "2c"):
        return CommunityData(cred.community, mpModel=0 if cred.version == "1" else 1)

    kwargs = {}
    if cred.auth_key:
        kwargs["authProtocol"] = auth_protos.get(cred.auth_proto.upper(), usmHMACSHAAuthProtocol)
        kwargs["authKey"] = cred.auth_key
    if cred.priv_key:
        kwargs["privProtocol"] = priv_protos.get(cred.priv_proto.upper(), usmAesCfb128Protocol)
        kwargs["privKey"] = cred.priv_key
    return UsmUserData(cred.user, **kwargs)


async def _construir_target(host, port, timeout, retries):
    from pysnmp.hlapi.asyncio import UdpTransportTarget
    if hasattr(UdpTransportTarget, "create"):  # pysnmp 7.x
        return await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    return UdpTransportTarget((host, port), timeout=timeout, retries=retries)  # pysnmp 6.x


def snmp_get(host: str, port: int, cred: Credenciales, oids: dict[str, str],
             timeout: float, retries: int) -> tuple[bool, dict[str, object], str | None]:
    """GET de varios OIDs. Devuelve (ok, {nombre: valor}, error)."""
    return asyncio.run(_snmp_get_async(host, port, cred, oids, timeout, retries))


async def _snmp_get_async(host, port, cred, oids, timeout, retries):
    from pysnmp.hlapi.asyncio import (
        ContextData, ObjectIdentity, ObjectType, SnmpEngine,
    )
    try:
        from pysnmp.hlapi.asyncio import get_cmd as _get_cmd   # pysnmp 7.x
    except ImportError:
        from pysnmp.hlapi.asyncio import getCmd as _get_cmd     # pysnmp 6.x

    from pysnmp.proto import rfc1905  # valores especiales de OID no existente

    auth_data = _construir_auth(cred)
    target = await _construir_target(host, port, timeout, retries)
    nombres = list(oids.keys())
    objetos = [ObjectType(ObjectIdentity(oids[n])) for n in nombres]

    error_indication, error_status, error_index, var_binds = await _get_cmd(
        SnmpEngine(), auth_data, target, ContextData(), *objetos
    )

    _no_existe = (rfc1905.NoSuchObject, rfc1905.NoSuchInstance, rfc1905.EndOfMibView)
    valores: dict[str, object] = {}
    error: str | None = None
    if error_indication:
        error = str(error_indication)
    elif error_status:
        error = f"{error_status.prettyPrint()} (idx {error_index})"
    else:
        for nombre, vb in zip(nombres, var_binds):
            # Saltar OIDs no soportados por el agente (no son valores reales).
            if isinstance(vb[1], _no_existe):
                continue
            valores[nombre] = vb[1]

    ok = error is None and bool(valores)
    return ok, valores, error


def snmp_walk(host: str, port: int, cred: Credenciales, base_oid: str,
              timeout: float, retries: int) -> tuple[list[tuple[str, object]], str | None]:
    """WALK de un subárbol. Devuelve ([(oid, valor), ...], error)."""
    return asyncio.run(_snmp_walk_async(host, port, cred, base_oid, timeout, retries))


async def _snmp_walk_async(host, port, cred, base_oid, timeout, retries):
    from pysnmp.hlapi.asyncio import (
        ContextData, ObjectIdentity, ObjectType, SnmpEngine,
    )
    try:
        from pysnmp.hlapi.asyncio import walk_cmd as _walk_cmd   # pysnmp 7.x
    except ImportError:
        from pysnmp.hlapi.asyncio import walkCmd as _walk_cmd     # pysnmp 6.x

    auth_data = _construir_auth(cred)
    target = await _construir_target(host, port, timeout, retries)

    resultados: list[tuple[str, object]] = []
    error: str | None = None
    objeto = ObjectType(ObjectIdentity(base_oid))

    async for (err_ind, err_stat, err_idx, var_binds) in _walk_cmd(
        SnmpEngine(), auth_data, target, ContextData(), objeto, lexicographicMode=False
    ):
        if err_ind:
            error = str(err_ind); break
        if err_stat:
            error = f"{err_stat.prettyPrint()} (idx {err_idx})"; break
        for vb in var_binds:
            resultados.append((str(vb[0]), vb[1]))

    return resultados, error
