-- =====================================================================
-- 0012_config_respaldos.up.sql
-- Respaldo de configuración de equipos (estilo Oxidized/RANCID): guarda la
-- config completa cuando CAMBIA, con su diff respecto a la versión anterior.
-- Lo escribe el worker (job diario). MVP: FortiGate vía API REST.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS config_respaldos (
  id         bigserial PRIMARY KEY,
  recurso_id bigint NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  ts         timestamptz NOT NULL DEFAULT now(),
  hash       text NOT NULL,            -- sha256 del contenido (para detectar cambios)
  bytes      integer,
  cambio     boolean NOT NULL DEFAULT false,  -- ¿difiere de la versión anterior?
  diff       text,                     -- diff unificado vs la versión previa
  contenido  text NOT NULL             -- la configuración completa
);

CREATE INDEX IF NOT EXISTS idx_config_respaldos ON config_respaldos(recurso_id, ts DESC);

COMMENT ON TABLE config_respaldos IS 'Versiones de configuración de equipos (solo se guarda al cambiar).';

COMMIT;
