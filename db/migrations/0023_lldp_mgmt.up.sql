-- =====================================================================
-- 0023_lldp_mgmt.up.sql
-- Topología: guardar la DIRECCIÓN DE GESTIÓN del vecino LLDP (lldpRemManAddr).
-- Permite enlazar el vecino a un recurso conocido por su IP de gestión, no solo
-- por sysName (que rara vez coincide con el nombre del recurso en SIMON).
-- =====================================================================
BEGIN;
ALTER TABLE lldp_vecinos ADD COLUMN IF NOT EXISTS remote_mgmt text;
COMMENT ON COLUMN lldp_vecinos.remote_mgmt IS 'IP de gestión anunciada por el vecino (lldpRemManAddr).';
COMMIT;
