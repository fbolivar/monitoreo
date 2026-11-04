"""Tests del parser puro de syslog."""
from monitor.syslog_parse import parse_syslog, severidad_de


def test_severidad_mapeo():
    assert severidad_de(0) == "critical"   # emergency
    assert severidad_de(3) == "critical"   # error
    assert severidad_de(4) == "warning"
    assert severidad_de(6) == "info"


def test_rfc3164_con_tag():
    # <189> = facility 23, severity 5 (notice)
    r = parse_syslog("<189>Oct 11 22:14:15 sw-core-01 %LINK-3-UPDOWN: Interface Gi0/1 down")
    assert r["facility"] == 23
    assert r["severidad_syslog"] == 5
    assert r["severidad"] == "info"
    assert r["hostname"] == "sw-core-01"
    assert r["app"] == "%LINK-3-UPDOWN"
    assert "Interface Gi0/1 down" in r["mensaje"]


def test_rfc3164_error_es_critical():
    # <185> = facility 23, severity 1 (alert) -> critical
    r = parse_syslog("<185>Oct 11 22:14:15 rtr1 bgp: neighbor 10.0.0.1 Down")
    assert r["severidad"] == "critical"
    assert r["hostname"] == "rtr1" and r["app"] == "bgp"


def test_rfc5424():
    r = parse_syslog("<34>1 2026-11-03T22:14:15Z fw01 sshd 1234 ID47 - Failed password for root")
    assert r["facility"] == 4 and r["severidad_syslog"] == 2 and r["severidad"] == "critical"
    assert r["hostname"] == "fw01" and r["app"] == "sshd"
    assert r["mensaje"] == "Failed password for root"


def test_rfc5424_nilvalues():
    r = parse_syslog("<13>1 2026-11-03T22:14:15Z host1 - - - - mensaje suelto")
    assert r["hostname"] == "host1" and r["app"] is None
    assert r["mensaje"] == "mensaje suelto"


def test_sin_formato():
    r = parse_syslog("texto plano sin pri")
    assert r["mensaje"] == "texto plano sin pri" and r["severidad"] == "info"
