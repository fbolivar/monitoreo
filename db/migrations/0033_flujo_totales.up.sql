-- =====================================================================
-- 0033_flujo_totales.up.sql — Totales agregados de NetFlow por ventana.
-- A diferencia de `flujos` (que guarda solo el TOP-N de conversaciones), esta
-- tabla guarda el agregado de TODO el tráfico por (ventana, app, protocolo),
-- con app colapsada a un conjunto acotado (los 'port-*' desconocidos -> 'otros').
-- Da KPIs/ancho de banda/protocolos/serie REALES. Cardinalidad acotada.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS flujo_totales (
  id              bigserial PRIMARY KEY,
  exporter_ip     inet,
  recurso_id      bigint REFERENCES recursos(id) ON DELETE SET NULL,
  ventana_inicio  timestamptz NOT NULL,
  ventana_fin     timestamptz NOT NULL DEFAULT now(),
  app             text,
  protocolo       smallint,
  bytes           bigint NOT NULL DEFAULT 0,
  paquetes        bigint NOT NULL DEFAULT 0,
  flujos          integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_flujo_totales_ventana ON flujo_totales(ventana_fin DESC);
CREATE INDEX IF NOT EXISTS idx_flujo_totales_recurso ON flujo_totales(recurso_id, ventana_fin DESC);

COMMENT ON TABLE flujo_totales IS 'Agregado de TODO el tráfico NetFlow por ventana/app/protocolo (totales reales). Lo escribe simon-netflow.';

COMMIT;
