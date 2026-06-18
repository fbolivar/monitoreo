-- Revierte 0024_flujos_wan.up.sql
BEGIN;
DROP TABLE IF EXISTS wan_calidad;
DROP TABLE IF EXISTS flujos;
COMMIT;
