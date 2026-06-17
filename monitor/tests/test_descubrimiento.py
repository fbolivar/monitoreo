"""Tests de la lógica pura del auto-descubrimiento (descubrimiento.py)."""
from monitor.descubrimiento import clasificar, expandir_subred


# ── expandir_subred ───────────────────────────────────────────────────
def test_cidr_24_excluye_red_y_broadcast():
    ips = expandir_subred("192.168.10.0/24")
    assert len(ips) == 254
    assert "192.168.10.1" in ips
    assert "192.168.10.254" in ips
    assert "192.168.10.0" not in ips
    assert "192.168.10.255" not in ips


def test_ip_suelta():
    assert expandir_subred("10.0.0.5") == ["10.0.0.5"]


def test_cidr_30_incluye_los_dos_hosts():
    ips = expandir_subred("192.168.1.4/30")
    assert ips == ["192.168.1.5", "192.168.1.6"]


def test_cidr_31_punto_a_punto():
    # /31 (RFC 3021): los dos addresses son utilizables.
    assert expandir_subred("10.0.0.0/31") == ["10.0.0.0", "10.0.0.1"]


def test_cidr_32_un_solo_host():
    assert expandir_subred("10.0.0.7/32") == ["10.0.0.7"]


def test_subred_demasiado_grande_devuelve_vacio():
    assert expandir_subred("10.0.0.0/8") == []
    assert expandir_subred("10.0.0.0/16", max_hosts=1024) == []


def test_subred_grande_con_tope_holgado():
    assert len(expandir_subred("10.0.0.0/16", max_hosts=70000)) == 65534


def test_invalida_o_vacia():
    assert expandir_subred("no-es-una-ip") == []
    assert expandir_subred("") == []
    assert expandir_subred("192.168.1.0/99") == []


# ── clasificar ────────────────────────────────────────────────────────
def test_fortiswitch_gana_a_fortinet_por_keyword():
    # FortiSwitch debe clasificar como switch, no como firewall.
    assert clasificar("FortiSwitch-148F v7.2", None) == "switch_lan"


def test_fortigate_es_firewall():
    assert clasificar("FortiGate-100F", "1.3.6.1.4.1.12356.101.1") == "firewall"


def test_windows_es_servidor():
    assert clasificar("Hardware: Intel64 ... Windows Version 6.3", None) == "servidor"


def test_dell_os9_switch_por_keyword():
    assert clasificar("Dell Networking OS9 Force10", None) == "switch_lan"


def test_synology_nas():
    assert clasificar("Synology DSM", None) == "nas"


def test_linux_gana_a_synology_por_orden_de_keywords():
    # 'linux' aparece antes que 'synology' en la lista de keywords, así que un
    # sysDescr que contenga ambos clasifica como servidor (limitación conocida).
    assert clasificar("Linux DiskStation Synology", None) == "servidor"


def test_clasifica_por_enterprise_cuando_no_hay_keyword():
    # sysDescr genérico sin palabras clave -> usa el número de empresa del OID.
    assert clasificar("Some Device", "1.3.6.1.4.1.318.1.3") == "ups"      # APC
    assert clasificar(None, "1.3.6.1.4.1.9.1.2055") == "switch_lan"        # Cisco
    assert clasificar(None, "1.3.6.1.4.1.6574.1") == "nas"                 # Synology


def test_desconocido_devuelve_none():
    assert clasificar(None, None) is None
    assert clasificar("Aparato raro", "1.3.6.1.4.1.99999.1") is None
    assert clasificar("", "") is None
