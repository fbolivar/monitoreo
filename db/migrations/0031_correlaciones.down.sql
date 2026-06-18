BEGIN;
ALTER TABLE incidencias DROP COLUMN IF EXISTS correlacion_id;
DROP TABLE IF EXISTS correlaciones;
COMMIT;
