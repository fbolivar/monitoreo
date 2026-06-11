-- =====================================================================
-- 0005_dependencias.up.sql
-- Dependencia padre→hijo entre recursos. Si el recurso padre (p.ej. el enlace
-- WAN o el firewall de una sede) está 'down', el worker suprime las incidencias
-- y notificaciones de los hijos (evita tormentas de alertas).
-- =====================================================================
BEGIN;

ALTER TABLE recursos
  ADD COLUMN IF NOT EXISTS depende_de_id bigint REFERENCES recursos(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_recursos_depende_de ON recursos(depende_de_id);

COMMENT ON COLUMN recursos.depende_de_id IS
  'Recurso del que depende (enlace/firewall/switch aguas arriba). Si ese ancestro está down, se silencian las alertas de este recurso.';

COMMIT;
