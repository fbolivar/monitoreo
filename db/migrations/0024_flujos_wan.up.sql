-- =====================================================================
-- 0024_flujos_wan.up.sql
-- Ola de visibilidad de red:
--  (1) flujos      — análisis de tráfico NetFlow v5/v9 / IPFIX exportado por
--      el FortiGate (y switches). Guarda TOP conversaciones agregadas por
--      ventana (no flujo crudo: sería ingobernable). Lo escribe el servicio
--      simon-netflow (colector UDP), no la API ni el worker de sondeo.
--  (4) wan_calidad — calidad activa de enlaces WAN/Starlink: latencia, jitter,
--      pérdida, throughput (iperf3) y MOS estimado (E-model). Lo escribe el job
--      medir_calidad_wan del worker para los recursos opt-in.
-- =====================================================================
BEGIN;

-- (1) Flujos agregados (top conversaciones por ventana de tiempo).
CREATE TABLE IF NOT EXISTS flujos (
  id              bigserial PRIMARY KEY,
  exporter_ip     inet,                       -- equipo que exportó (FortiGate/switch)
  recurso_id      bigint REFERENCES recursos(id) ON DELETE SET NULL,
  ventana_inicio  timestamptz NOT NULL,
  ventana_fin     timestamptz NOT NULL DEFAULT now(),
  src_ip          inet,
  dst_ip          inet,
  src_port        integer,
  dst_port        integer,
  protocolo       smallint,                   -- 6=TCP 17=UDP 1=ICMP ...
  app             text,                        -- derivada del puerto (https, dns, ...)
  bytes           bigint NOT NULL DEFAULT 0,
  paquetes        bigint NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_flujos_ventana ON flujos(ventana_fin DESC);
CREATE INDEX IF NOT EXISTS idx_flujos_recurso ON flujos(recurso_id, ventana_fin DESC);
CREATE INDEX IF NOT EXISTS idx_flujos_app ON flujos(app);

COMMENT ON TABLE flujos IS 'Top conversaciones de tráfico (NetFlow/IPFIX) agregadas por ventana. Las escribe simon-netflow.';

-- (4) Calidad de enlace WAN (medición activa).
CREATE TABLE IF NOT EXISTS wan_calidad (
  id            bigserial PRIMARY KEY,
  recurso_id    bigint NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  ts            timestamptz NOT NULL DEFAULT now(),
  latency_ms    numeric(8,2),
  jitter_ms     numeric(8,2),
  loss_pct      numeric(5,2),
  down_mbps     numeric(10,2),    -- throughput de bajada (iperf3), null si no se midió
  up_mbps       numeric(10,2),    -- throughput de subida
  mos           numeric(3,2),     -- 1.00–4.50 (E-model simplificado)
  calidad       text              -- buena | aceptable | mala
);

CREATE INDEX IF NOT EXISTS idx_wan_calidad_recurso ON wan_calidad(recurso_id, ts DESC);

COMMENT ON TABLE wan_calidad IS 'Mediciones activas de calidad WAN/Starlink (throughput + MOS). Las escribe el job medir_calidad_wan.';

COMMIT;
