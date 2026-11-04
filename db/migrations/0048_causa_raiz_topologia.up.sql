-- =====================================================================
-- 0048_causa_raiz_topologia.up.sql
-- Causa raíz por TOPOLOGÍA (NOC P1-4). Convierte el LLDP ya recolectado en una
-- dependencia AUTOMÁTICA, sin configurarla a mano:
--   * recursos.es_nucleo       -> marca el/los nodo(s) raíz (core/gateway).
--   * recursos.padre_topologia_id -> padre hacia la raíz, calculado por el worker
--     a partir del grafo LLDP (BFS desde las raíces).
-- La lógica de supresión y correlación usa COALESCE(depende_de_id, padre_topologia_id):
-- la dependencia MANUAL pisa a la topológica; donde no hay manual, manda la topología.
-- =====================================================================
BEGIN;

ALTER TABLE recursos
  ADD COLUMN IF NOT EXISTS es_nucleo boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS padre_topologia_id bigint REFERENCES recursos(id) ON DELETE SET NULL;

COMMENT ON COLUMN recursos.es_nucleo          IS 'Nodo raíz de la topología (core/gateway) para la causa raíz automática.';
COMMENT ON COLUMN recursos.padre_topologia_id IS 'Padre hacia la raíz derivado del LLDP (lo calcula el worker; NULL = raíz o sin topología).';

COMMIT;
