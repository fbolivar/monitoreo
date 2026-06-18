-- =====================================================================
-- 0030_rum.up.sql — APM real: RUM + trazas (#13)
-- "Camino B" de observabilidad: experiencia REAL del usuario (Real User
-- Monitoring) vía un beacon JS, y trazas distribuidas (spans, estilo OTel).
-- Ingesta pública con token opcional en /api/ingest/rum y /api/ingest/span.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS rum_eventos (
  id          bigserial PRIMARY KEY,
  ts          timestamptz NOT NULL DEFAULT now(),
  url         text,
  tipo        text NOT NULL DEFAULT 'pageload',  -- pageload | paint | error
  valor_ms    numeric(10,2),                       -- load time / FCP / etc.
  navegador   text,
  sitio       text                                 -- etiqueta libre (app/cliente)
);
CREATE INDEX IF NOT EXISTS idx_rum_ts ON rum_eventos(ts DESC);
CREATE INDEX IF NOT EXISTS idx_rum_url ON rum_eventos(url);

CREATE TABLE IF NOT EXISTS spans (
  id          bigserial PRIMARY KEY,
  ts          timestamptz NOT NULL DEFAULT now(),
  trace_id    text,
  span_id     text,
  parent_id   text,
  nombre      text,
  servicio    text,
  dur_ms      numeric(10,2)
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_ts ON spans(ts DESC);

COMMENT ON TABLE rum_eventos IS 'Real User Monitoring: tiempos reales de carga del navegador del usuario.';
COMMENT ON TABLE spans IS 'Trazas distribuidas (estilo OpenTelemetry) ingeridas por la API.';

COMMIT;
