"""Cliente SNMP aislado (la ÚNICA parte dependiente de pysnmp y de su versión).

Soporta SNMP v1/v2c (community) y v3 (USM: noAuth/authNoPriv/authPriv).
La E/S se hace con la API asyncio de pysnmp envuelta en asyncio.run(), apta
para ejecutarse dentro de los hilos de APScheduler.
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
        """Nivel USM derivado de las claves presentes (solo informativo/tests)."""
        if self.version != "3":
            return "n/a"
        if self.auth_key and self.priv_key:
            return "authPriv"
        if self.auth_key:
            return "authNoPriv"
        return "noAuthNoPriv"


def snmp_get(host: str, port: int, cred: Credenciales, oids: dict[str, str],
             timeout: float, retries: int) -> tuple[bool, dict[str, object], str | None]:
    """GET sincrónico de varios OIDs. Devuelve (ok, {nombre: valor}, error)."""
    return asyncio.run(_snmp_get_async(host, port, cred, oids, timeout, retries))


async def _snmp_get_async(host, port, cred, oids, timeout, retries):
    from pysnmp.hlapi.asyncio import (  # import diferido: dependencia de ejecución
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        UsmUserData,
        get_cmd,
        usmAesCfb128Protocol,
        usmDESPrivProtocol,
        usmHMACMD5AuthProtocol,
        usmHMACSHAAuthProtocol,
    )

    auth_protos = {"MD5": usmHMACMD5AuthProtocol, "SHA": usmHMACSHAAuthProtocol}
    priv_protos = {"DES": usmDESPrivProtocol, "AES": usmAesCfb128Protocol}

    if cred.version in ("1", "2c"):
        auth_data = CommunityData(cred.community, mpModel=0 if cred.version == "1" else 1)
    else:
        kwargs = {}
        if cred.auth_key:
            kwargs["authProtocol"] = auth_protos.get(cred.auth_proto.upper(), usmHMACSHAAuthProtocol)
            kwargs["authKey"] = cred.auth_key
        if cred.priv_key:
            kwargs["privProtocol"] = priv_protos.get(cred.priv_proto.upper(), usmAesCfb128Protocol)
            kwargs["privKey"] = cred.priv_key
        auth_data = UsmUserData(cred.user, **kwargs)

    target = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    nombres = list(oids.keys())
    objetos = [ObjectType(ObjectIdentity(oids[n])) for n in nombres]

    error_indication, error_status, error_index, var_binds = await get_cmd(
        SnmpEngine(), auth_data, target, ContextData(), *objetos
    )

    valores: dict[str, object] = {}
    error: str | None = None
    if error_indication:
        error = str(error_indication)
    elif error_status:
        error = f"{error_status.prettyPrint()} (idx {error_index})"
    else:
        for nombre, vb in zip(nombres, var_binds):
            valores[nombre] = vb[1]

    ok = error is None and bool(valores)
    return ok, valores, error
