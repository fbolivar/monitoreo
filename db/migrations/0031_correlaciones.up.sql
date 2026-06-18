-- =====================================================================
-- 0031_correlaciones.up.sql — AIOps: correlación de alertas (#14)
-- Agrupa incidencias abiertas relacionadas (misma sede + ventana de tiempo,
-- o cadena de dependencia) en UN evento, marcando la causa raíz probable.
-- Reduce el ruido: 10 alertas de un parque = 1 evento "se cayó el enlace".
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS correlaciones (
  id                bigserial PRIMARY KEY,
  creada_at         timestamptz NOT NULL DEFAULT now(),
  actualizada_at    timestamptz NOT NULL DEFAULT now(),
  sitio_id          integer REFERENCES sitios(id) ON DELETE SET NULL,
  causa_incidencia_id bigint REFERENCES incidencias(id) ON DELETE SET NULL,
  resumen           text,
  n_incidencias     integer NOT NULL DEFAULT 0,
  abierta           boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_correlaciones_abierta ON correlaciones(abierta, creada_at DESC);

ALTER TABLE incidencias ADD COLUMN IF NOT EXISTS correlacion_id bigint
  REFERENCES correlaciones(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_incidencias_correlacion ON incidencias(correlacion_id);

COMMENT ON TABLE correlaciones IS 'Grupos de incidencias correlacionadas (AIOps, reducción de ruido).';

COMMIT;
