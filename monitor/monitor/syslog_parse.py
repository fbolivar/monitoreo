"""Parseo PURO de mensajes syslog (RFC 3164 y RFC 5424), sin red ni BD.

Un datagrama syslog empieza con el PRI `<N>` donde N = facility*8 + severity.
- RFC 5424:  <PRI>1 TIMESTAMP HOST APP PROCID MSGID [SD] MSG
- RFC 3164:  <PRI>Mmm dd hh:mm:ss HOST TAG[pid]: MSG   (TAG opcional)

`parse_syslog` devuelve un dict normalizado:
  {facility, severidad_syslog, severidad, hostname, app, mensaje}
`severidad` mapea la severidad syslog (0..7) a la nuestra (info/warning/critical).
"""
from __future__ import annotations

import re

# syslog severity (0..7) -> severidad propia. 0-3 (emerg,alert,crit,err)=critical,
# 4 (warning)=warning, 5-7 (notice,info,debug)=info.
def severidad_de(sev_syslog: int) -> str:
    if sev_syslog <= 3:
        return "critical"
    if sev_syslog == 4:
        return "warning"
    return "info"


_PRI = re.compile(r"^<(\d{1,3})>")
# RFC5424: tras el PRI viene "1 " (versión) y luego timestamp host app procid ...
_RFC5424 = re.compile(
    r"^1\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(?:\[.*?\]|-)\s*(.*)$", re.DOTALL)
# RFC3164: "Mmm dd hh:mm:ss host tag: msg"
_RFC3164 = re.compile(
    r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)\s+(.*)$", re.DOTALL)
_TAG = re.compile(r"^([^:\[\s]{1,48})(?:\[\d+\])?:\s*(.*)$", re.DOTALL)


def _nd(v: str) -> str | None:
    """RFC5424 usa '-' como NILVALUE."""
    return None if v in ("-", "") else v


def parse_syslog(raw: str) -> dict:
    raw = (raw or "").strip()
    out = {"facility": None, "severidad_syslog": None, "severidad": "info",
           "hostname": None, "app": None, "mensaje": raw}

    m = _PRI.match(raw)
    resto = raw
    if m:
        pri = int(m.group(1))
        out["facility"] = pri // 8
        sev = pri % 8
        out["severidad_syslog"] = sev
        out["severidad"] = severidad_de(sev)
        resto = raw[m.end():]

    # RFC 5424 (empieza por la versión "1 ")
    m5 = _RFC5424.match(resto)
    if m5:
        _ts, host, app, _procid, _msgid, msg = m5.groups()
        out["hostname"] = _nd(host)
        out["app"] = _nd(app)
        out["mensaje"] = msg.strip()
        return out

    # RFC 3164
    m3 = _RFC3164.match(resto)
    if m3:
        host, tagmsg = m3.groups()
        out["hostname"] = host
        mt = _TAG.match(tagmsg)
        if mt:
            out["app"] = mt.group(1)
            out["mensaje"] = mt.group(2).strip()
        else:
            out["mensaje"] = tagmsg.strip()
        return out

    # Sin formato reconocible: deja el resto (sin PRI) como mensaje.
    out["mensaje"] = resto.strip() or raw
    return out
