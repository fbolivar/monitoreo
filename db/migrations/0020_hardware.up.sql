-- =====================================================================
-- 0020_hardware.up.sql
-- Monitoreo de hardware físico (out-of-band) vía Redfish (REST/HTTPS) con
-- fallback IPMI. Lee del BMC (iDRAC/iLO/XCC/Supermicro) la salud del chasis:
-- fuentes, temperaturas, ventiladores, almacenamiento/RAID, y el inventario
-- (modelo, serial, firmware, CPU, memoria). NO instrumenta el SO del servidor.
--
-- Opt-in por recurso: `parametros.hardware` = {protocolo:'auto'|'redfish'|'ipmi',
--   bmc_host?:'ip', verify_tls?:false}. Credenciales del BMC en `secretos`
--   (bmc_user / bmc_password), cifradas con pgcrypto como el resto.
-- =====================================================================
BEGIN;

-- Snapshot del estado de cada componente físico (se reemplaza en cada sondeo).
CREATE TABLE IF NOT EXISTS hardware_componentes (
  id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recurso_id    bigint      NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  categoria     text        NOT NULL,   -- power | thermal | fan | storage | memory | processor | chassis
  nombre        text        NOT NULL,   -- p.ej. 'PSU 1', 'CPU1 Temp', 'Fan 3A', 'Disk 0:1:2'
  estado        text        NOT NULL DEFAULT 'unknown'
                  CHECK (estado IN ('up','degraded','down','unknown')),
  lectura       double precision,       -- valor numérico si aplica (°C, RPM, W)
  unidad        text,                   -- '°C' | 'RPM' | 'W' | '%' | NULL
  detalle       jsonb       NOT NULL DEFAULT '{}'::jsonb,  -- modelo/serial/capacidad/estado crudo
  actualizado_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE hardware_componentes IS 'Salud de componentes físicos (Redfish/IPMI); snapshot por recurso.';
CREATE UNIQUE INDEX IF NOT EXISTS uq_hw_componente
  ON hardware_componentes(recurso_id, categoria, nombre);
CREATE INDEX IF NOT EXISTS idx_hw_componente_recurso ON hardware_componentes(recurso_id, categoria);

-- Inventario del equipo (una fila por recurso).
CREATE TABLE IF NOT EXISTS hardware_inventario (
  recurso_id     bigint      PRIMARY KEY REFERENCES recursos(id) ON DELETE CASCADE,
  fabricante     text,
  modelo         text,
  serial         text,
  sku            text,
  bios_version   text,
  bmc_firmware   text,
  cpu_modelo     text,
  cpu_cantidad   integer,
  memoria_gb     double precision,
  power_state    text,                  -- On | Off
  salud_global   text,                  -- up | degraded | down | unknown
  protocolo      text,                  -- redfish | ipmi
  detalle        jsonb       NOT NULL DEFAULT '{}'::jsonb,
  actualizado_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE hardware_inventario IS 'Inventario físico y salud global del equipo (Redfish/IPMI).';

COMMIT;
