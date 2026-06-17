"""Tests de los parsers puros de hardware (Redfish + IPMI) y la combinación de salud."""
from monitor.hardware import peor_estado
from monitor.probes import ipmi_probe, redfish


# ── Redfish: mapeo de estado ──────────────────────────────────────────
def test_estado_de_health():
    assert redfish.estado_de({"Health": "OK", "State": "Enabled"}) == "up"
    assert redfish.estado_de({"Health": "Warning", "State": "Enabled"}) == "degraded"
    assert redfish.estado_de({"Health": "Critical", "State": "Enabled"}) == "down"
    assert redfish.estado_de({"State": "Absent"}) == "unknown"
    assert redfish.estado_de(None) == "unknown"
    assert redfish.estado_de({}) == "unknown"


def test_estado_ausente_no_es_fallo():
    # Un slot vacío (PSU no instalada) no debe contar como caído.
    assert redfish.estado_de({"Health": None, "State": "Absent"}) == "unknown"


# ── Redfish: inventario ───────────────────────────────────────────────
def test_parse_system():
    sysj = {
        "Manufacturer": "Dell Inc.", "Model": "PowerEdge R740", "SerialNumber": "ABC123",
        "SKU": "SVC-TAG", "BiosVersion": "2.10.2", "PowerState": "On",
        "ProcessorSummary": {"Count": 2, "Model": "Intel Xeon Gold 6230"},
        "MemorySummary": {"TotalSystemMemoryGiB": 384},
        "Status": {"Health": "OK", "State": "Enabled"},
        "HostName": "esxi01",
    }
    inv = redfish.parse_system(sysj)
    assert inv["fabricante"] == "Dell Inc."
    assert inv["modelo"] == "PowerEdge R740"
    assert inv["serial"] == "ABC123"
    assert inv["cpu_cantidad"] == 2
    assert inv["memoria_gb"] == 384.0
    assert inv["power_state"] == "On"
    assert inv["salud_global"] == "up"


# ── Redfish: térmico ──────────────────────────────────────────────────
def test_parse_thermal_temps_y_fans():
    thermal = {
        "Temperatures": [
            {"Name": "CPU1 Temp", "ReadingCelsius": 45, "Status": {"Health": "OK", "State": "Enabled"},
             "UpperThresholdCritical": 95},
            {"Name": "Inlet Temp", "ReadingCelsius": 80, "Status": {"Health": "Warning", "State": "Enabled"}},
            {"Name": "Sensor ausente", "Status": {"State": "Absent"}},  # se omite
        ],
        "Fans": [
            {"Name": "Fan1A", "Reading": 6000, "ReadingUnits": "RPM", "Status": {"Health": "OK", "State": "Enabled"}},
            {"Name": "Fan2B", "Reading": 0, "Status": {"Health": "Critical", "State": "Enabled"}},
        ],
    }
    comps = redfish.parse_thermal(thermal)
    temps = [c for c in comps if c["categoria"] == "thermal"]
    fans = [c for c in comps if c["categoria"] == "fan"]
    assert len(temps) == 2  # el ausente se omitió
    assert {"CPU1 Temp", "Inlet Temp"} == {c["nombre"] for c in temps}
    cpu = next(c for c in temps if c["nombre"] == "CPU1 Temp")
    assert cpu["lectura"] == 45.0 and cpu["unidad"] == "°C" and cpu["estado"] == "up"
    inlet = next(c for c in temps if c["nombre"] == "Inlet Temp")
    assert inlet["estado"] == "degraded"
    assert len(fans) == 2
    assert next(c for c in fans if c["nombre"] == "Fan2B")["estado"] == "down"


# ── Redfish: energía ──────────────────────────────────────────────────
def test_parse_power():
    power = {
        "PowerSupplies": [
            {"Name": "PSU1", "Status": {"Health": "OK", "State": "Enabled"},
             "PowerInputWatts": 230, "Model": "PWR-750", "SerialNumber": "PS1"},
            {"Name": "PSU2", "Status": {"Health": "Critical", "State": "Enabled"},
             "LastPowerOutputWatts": 0},
        ],
        "PowerControl": [{"Name": "System Power", "PowerConsumedWatts": 410}],
    }
    comps = redfish.parse_power(power)
    psus = [c for c in comps if c["categoria"] == "power"]
    chassis = [c for c in comps if c["categoria"] == "chassis"]
    assert len(psus) == 2
    psu1 = next(c for c in psus if c["nombre"] == "PSU1")
    assert psu1["lectura"] == 230.0 and psu1["detalle"]["modelo"] == "PWR-750"
    assert next(c for c in psus if c["nombre"] == "PSU2")["estado"] == "down"
    assert chassis and chassis[0]["lectura"] == 410.0


# ── Redfish: almacenamiento ───────────────────────────────────────────
def test_parse_storage():
    storage = [{
        "StorageControllers": [{"Name": "PERC H740P", "Model": "H740P", "FirmwareVersion": "51.x",
                                "Status": {"Health": "OK", "State": "Enabled"}}],
        "Drives": [
            {"Name": "Disk 0", "Status": {"Health": "OK", "State": "Enabled"},
             "CapacityBytes": 960000000000, "MediaType": "SSD"},
            {"Name": "Disk 1", "Status": {"Health": "Critical", "State": "Enabled"}},
        ],
        "Volumes": [{"Name": "VD0", "RAIDType": "RAID1", "Status": {"Health": "OK", "State": "Enabled"}}],
    }]
    comps = redfish.parse_storage(storage)
    nombres = {c["nombre"] for c in comps}
    assert "Ctrl PERC H740P" in nombres
    assert "Disk 0" in nombres and "Disk 1" in nombres
    assert "Vol VD0" in nombres
    disk0 = next(c for c in comps if c["nombre"] == "Disk 0")
    assert disk0["lectura"] == 960.0 and disk0["unidad"] == "GB"
    assert next(c for c in comps if c["nombre"] == "Disk 1")["estado"] == "down"


# ── Combinación de salud ──────────────────────────────────────────────
def test_peor_estado():
    assert peor_estado(["up", "up", "degraded"]) == "degraded"
    assert peor_estado(["up", "down", "degraded"]) == "down"
    assert peor_estado(["up", "up"]) == "up"
    assert peor_estado(["unknown", "unknown"]) == "unknown"
    assert peor_estado(["unknown", "up"]) == "up"
    assert peor_estado([]) == "unknown"


# ── IPMI: sensores ────────────────────────────────────────────────────
IPMI_SENSOR = """\
CPU1 Temp        | 45.000     | degrees C  | ok    | 0.000  | 0.000   | 0.000   | 95.000  | 99.000  | 105.000
Inlet Temp       | 78.000     | degrees C  | nc    | na     | na      | na      | 75.000  | 80.000  | 85.000
Fan1A            | 6000.000   | RPM        | ok    | na     | na      | na      | na      | na      | na
Fan2B            | 0.000      | RPM        | cr    | na     | na      | na      | na      | na      | na
PSU1 Status      | 0x0        | discrete   | 0x0100| na     | na      | na      | na      | na      | na
Pwr Consumption  | 410.000    | Watts      | ok    | na     | na      | na      | na      | na      | na
"""


def test_ipmi_parse_sensor():
    comps = ipmi_probe.parse_sensor(IPMI_SENSOR)
    por_nombre = {c["nombre"]: c for c in comps}
    assert por_nombre["CPU1 Temp"]["categoria"] == "thermal"
    assert por_nombre["CPU1 Temp"]["lectura"] == 45.0 and por_nombre["CPU1 Temp"]["estado"] == "up"
    assert por_nombre["Inlet Temp"]["estado"] == "degraded"   # nc
    assert por_nombre["Fan2B"]["estado"] == "down"            # cr
    assert por_nombre["Pwr Consumption"]["categoria"] == "power"
    # El sensor discreto 'PSU1 Status' (estado no mapeado) se omite.
    assert "PSU1 Status" not in por_nombre


def test_ipmi_parse_fru():
    fru = """\
 Product Manufacturer  : Supermicro
 Product Name          : SYS-1029U
 Product Serial        : S12345
 Product Part Number   : PN-9
"""
    inv = ipmi_probe.parse_fru(fru)
    assert inv["fabricante"] == "Supermicro"
    assert inv["modelo"] == "SYS-1029U"
    assert inv["serial"] == "S12345"
    assert inv["sku"] == "PN-9"


def test_ipmi_salud_global():
    assert ipmi_probe.salud_global([{"estado": "up"}, {"estado": "degraded"}]) == "degraded"
    assert ipmi_probe.salud_global([{"estado": "up"}, {"estado": "down"}]) == "down"
    assert ipmi_probe.salud_global([]) == "unknown"
