-- =====================================================================
-- 0023_lldp_mgmt.down.sql — Reversa de 0023.
-- =====================================================================
BEGIN;
ALTER TABLE lldp_vecinos DROP COLUMN IF EXISTS remote_mgmt;
COMMIT;
