-- =====================================================================
-- 0036_incidencia_notas.up.sql
-- Bitácora de la incidencia: notas del operador.
--
-- Motivo: una incidencia solo registraba quién la reconoció y cuándo se resolvió,
-- pero NO qué pasó ni qué se hizo. Ese conocimiento se perdía en cada turno: sin
-- relevo, sin post-mortem, sin historia para la próxima vez que falle lo mismo.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS incidencia_notas (
  id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  incidencia_id bigint      NOT NULL REFERENCES incidencias(id) ON DELETE CASCADE,
  perfil_id     uuid        REFERENCES perfiles(id) ON DELETE SET NULL,
  autor_email   text,                       -- se guarda plano: sobrevive al borrado del perfil
  nota          text        NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Se leen siempre por incidencia y en orden cronológico.
CREATE INDEX IF NOT EXISTS ix_incidencia_notas_inc ON incidencia_notas (incidencia_id, created_at);

COMMENT ON TABLE  incidencia_notas IS 'Bitácora del operador sobre una incidencia (diagnóstico, acciones, relevo de turno).';
COMMENT ON COLUMN incidencia_notas.autor_email IS 'Correo del autor en texto: la nota conserva autoría aunque se elimine el perfil.';

COMMIT;
