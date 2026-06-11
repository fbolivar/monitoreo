-- =====================================================================
-- 0006_auditoria.up.sql
-- Bitácora de auditoría: registra las acciones de gestión (crear/actualizar/
-- eliminar) por usuario sobre las entidades de configuración, además de logins
-- y acciones sobre incidencias. Para trazabilidad y cumplimiento.
-- La escriben los observers/controladores de la API (no el worker).
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS auditoria (
  id          bigserial PRIMARY KEY,
  ts          timestamptz NOT NULL DEFAULT now(),
  perfil_id   uuid REFERENCES perfiles(id) ON DELETE SET NULL,
  actor_email text,                 -- desnormalizado: sobrevive al borrado del perfil
  actor_rol   text,
  accion      text NOT NULL,        -- crear | actualizar | eliminar | login | login_fallido
  entidad     text NOT NULL,        -- recursos | sitios | umbrales | incidencias | perfiles | auth | ...
  entidad_id  text,
  descripcion text,                 -- etiqueta legible (nombre/email/métrica del objeto)
  cambios     jsonb,                -- {campo: [antes, despues]} en actualizaciones
  ip          inet
);

CREATE INDEX IF NOT EXISTS idx_auditoria_ts ON auditoria(ts DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_entidad ON auditoria(entidad, entidad_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_perfil ON auditoria(perfil_id);

COMMENT ON TABLE auditoria IS 'Bitácora de auditoría de acciones de gestión por usuario (cumplimiento).';

COMMIT;
