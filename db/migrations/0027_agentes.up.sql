-- =====================================================================
-- 0027_agentes.up.sql — Agente ligero Windows/Linux (#8)
-- Telemetría "desde dentro" del SO (procesos, servicios, disco por volumen)
-- que SNMP no da. El agente (psutil) hace POST autenticado por token a
-- /api/ingest/agente; las métricas caen en `metricas`, el inventario aquí.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS agentes (
  id          bigserial PRIMARY KEY,
  recurso_id  bigint REFERENCES recursos(id) ON DELETE SET NULL,
  nombre      text NOT NULL,
  token_hash  text NOT NULL UNIQUE,          -- sha256 del token (el token solo se ve al crear)
  hostname    text,
  so          text,
  version     text,
  last_seen   timestamptz,
  inventario  jsonb,                          -- snapshot: discos, servicios, top procesos
  activo      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agentes_recurso ON agentes(recurso_id);

COMMENT ON TABLE agentes IS 'Agentes ligeros (psutil) que reportan telemetría del SO por token.';

COMMIT;
