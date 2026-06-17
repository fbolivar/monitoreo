"""Tests de los helpers puros del respaldo de config por SSH."""
from monitor.probes.ssh_config import (
    comando_backup,
    comando_sin_paginacion,
    limpiar_salida,
)


# ── comando_backup ────────────────────────────────────────────────────
def test_comando_explicito_gana():
    p = {"backup": {"metodo": "ssh", "comando": "show config"}}
    assert comando_backup(p, "switch_lan") == "show config"


def test_comando_por_vendor():
    assert comando_backup({"backup": {"vendor": "dell_os9"}}) == "show running-config"
    assert comando_backup({"backup": {"vendor": "cisco"}}) == "show running-config"
    assert comando_backup({"backup": {"vendor": "fortiswitch"}}) == "show full-configuration"


def test_comando_default():
    assert comando_backup({}) == "show running-config"
    assert comando_backup({"backup": {}}, "switch_san") == "show running-config"


# ── comando_sin_paginacion ────────────────────────────────────────────
def test_sin_paginacion_default_y_vendor():
    assert comando_sin_paginacion({}) == "terminal length 0"
    assert comando_sin_paginacion({"backup": {"vendor": "fortiswitch"}}) == ""


def test_sin_paginacion_explicito_vacio():
    # El usuario puede forzar vacío (equipo sin paginador).
    assert comando_sin_paginacion({"backup": {"sin_paginacion": ""}}) == ""
    assert comando_sin_paginacion({"backup": {"sin_paginacion": "no pager"}}) == "no pager"


# ── limpiar_salida ────────────────────────────────────────────────────
def test_limpia_eco_pager_y_prompt():
    crudo = (
        "show running-configuration\r\n"
        "! Version 9.14\r\n"
        "hostname SW-CORE-01\r\n"
        "--More--\r\n"
        "interface Te 1/1\r\n"
        " no shutdown\r\n"
        "SW-CORE-01#\r\n"
    )
    out = limpiar_salida(crudo, "show running-configuration")
    lineas = out.split("\n")
    assert "show running-configuration" not in lineas      # eco quitado
    assert "--More--" not in out                            # pager quitado
    assert "SW-CORE-01#" not in lineas                      # prompt final quitado
    assert lineas[0] == "! Version 9.14"
    assert "hostname SW-CORE-01" in lineas
    assert "interface Te 1/1" in lineas


def test_limpia_recorta_vacias_extremos():
    out = limpiar_salida("\n\n  \nhostname X\n\n\n", "show run")
    assert out == "hostname X"


def test_prompt_con_espacios_no_se_quita():
    # Una línea de config que casualmente termina en '>' pero tiene espacios NO es prompt.
    out = limpiar_salida("banner motd >\nhostname X\n", "show run")
    assert "banner motd >" in out
