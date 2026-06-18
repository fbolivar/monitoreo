-- =====================================================================
-- 0032_glpi.up.sql — Integración con Mesa de Ayuda GLPI (#3, dejar lista)
-- Guarda el nº de ticket externo creado al abrir la incidencia. La creación
-- la hace un canal de notificación tipo 'glpi' (env-gated; sin credenciales
-- hasta que se configure el canal).
-- =====================================================================
BEGIN;

ALTER TABLE incidencias ADD COLUMN IF NOT EXISTS ticket_externo text;
COMMENT ON COLUMN incidencias.ticket_externo IS 'ID de ticket en la mesa de ayuda externa (GLPI), si se integró.';

COMMIT;
