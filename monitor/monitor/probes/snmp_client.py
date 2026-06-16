"""Cliente SNMP aislado (la ÚNICA parte dependiente de pysnmp y de su versión).

Soporta SNMP v1/v2c (community) y v3 (USM: noAuth/authNoPriv/authPriv), con GET
y WALK. Compatible con pysnmp 6.x (getCmd/walkCmd, UdpTransportTarget()) y
7.x (get_cmd/walk_cmd, UdpTransportTarget.create()).

RENDIMIENTO: el WALK usa GETBULK (bulkWalkCmd) en v2c/v3, que trae varios
varbinds por PDU (maxRepetitions) en vez de uno por GETNEXT. En tablas grandes
(IF-MIB de un switch con decenas de puertos) reduce ~20x el nº de round-trips y
de codificación/decodificación ASN.1 en Python — el verdadero coste de un chequeo
SNMP. SNMPv1 no soporta GETBULK, así que cae a GETNEXT (walkCmd).

Nota: pysnmp es CPU-bound en Python puro (ASN.1/MIB), así que el GIL limita el
paralelismo entre hebras a ~1.5x; la palanca real es REDUCIR el trabajo por
chequeo (GETBULK), no repartirlo entre más hebras.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

# maxRepetitions de GETBULK: varbinds por PDU. 25 equilibra round-trips vs
# tamaño de respuesta UDP (evita fragmentación excesiva).
_BULK_MAX_REP = 25


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


def _resolver_walk_cmd(version: str):
    """Devuelve (fn_walk, es_bulk). GETBULK en v2c/v3; GETNEXT en v1."""
    from pysnmp.hlapi import asyncio as hlapi
    if version != "1":  # v2c / v3 -> GETBULK
        fn = getattr(hlapi, "bulk_walk_cmd", None) or getattr(hlapi, "bulkWalkCmd", None)
        if fn is not None:
            return fn, True
    # v1 o sin soporte bulk -> GETNEXT
    fn = getattr(hlapi, "walk_cmd", None) or getattr(hlapi, "walkCmd")
    return fn, False


def snmp_walk(host: str, port: int, cred: Credenciales, base_oid: str,
              timeout: float, retries: int) -> tuple[list[tuple[str, object]], str | None]:
    """WALK de un subárbol (GETBULK en v2c/v3). Devuelve ([(oid, valor), ...], error)."""
    return asyncio.run(_snmp_walk_async(host, port, cred, base_oid, timeout, retries))


async def _snmp_walk_async(host, port, cred, base_oid, timeout, retries):
    from pysnmp.hlapi.asyncio import (
        ContextData, ObjectIdentity, ObjectType, SnmpEngine,
    )
    walk_cmd, es_bulk = _resolver_walk_cmd(cred.version)

    auth_data = _construir_auth(cred)
    target = await _construir_target(host, port, timeout, retries)
    objeto = ObjectType(ObjectIdentity(base_oid))
    engine = SnmpEngine()

    if es_bulk:
        # GETBULK: nonRepeaters=0, maxRepetitions=_BULK_MAX_REP.
        gen = walk_cmd(engine, auth_data, target, ContextData(),
                       0, _BULK_MAX_REP, objeto, lexicographicMode=False)
    else:
        gen = walk_cmd(engine, auth_data, target, ContextData(),
                       objeto, lexicographicMode=False)

    resultados: list[tuple[str, object]] = []
    error: str | None = None
    async for (err_ind, err_stat, err_idx, var_binds) in gen:
        if err_ind:
            error = str(err_ind); break
        if err_stat:
            error = f"{err_stat.prettyPrint()} (idx {err_idx})"; break
        for vb in var_binds:
            resultados.append((str(vb[0]), vb[1]))

    return resultados, error
