-- =====================================================================
-- 0018_servicios.up.sql
-- Observabilidad de servicios (Camino A): una "transacción observable" es una
-- cadena ordenada de componentes (Web → API Gateway → Catálogo → BD), cada uno
-- enlazado a un recurso que SIMON ya monitorea. La API correlaciona las latencias
-- de cada salto para: ubicar el cuello de botella (causa raíz), comparar la
-- experiencia extremo-a-extremo con un objetivo y mostrar el impacto al negocio.
-- Pasa de "el servidor está UP" a "por qué el usuario percibe lentitud y dónde".
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS servicios (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre          text        NOT NULL,
  descripcion     text,
  objetivo_ms     integer     NOT NULL DEFAULT 2000     -- SLA de experiencia (umbral "alto impacto")
                    CHECK (objetivo_ms > 0),
  impacto_negocio text,                                 -- nota libre (conversión/ventas/usuarios)
  activo          boolean     NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE servicios IS 'Transacción observable (cadena de componentes con un objetivo de experiencia).';

CREATE TABLE IF NOT EXISTS servicio_componentes (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  servicio_id bigint      NOT NULL REFERENCES servicios(id) ON DELETE CASCADE,
  orden       smallint    NOT NULL DEFAULT 0,           -- posición en la cadena
  nombre      text        NOT NULL,                     -- "Web", "API Gateway", "Catálogo", "Base de Datos"
  tipo        text        NOT NULL DEFAULT 'servicio'
                CHECK (tipo IN ('web','api','gateway','cache','db','externo','servicio')),
  recurso_id  bigint      REFERENCES recursos(id) ON DELETE SET NULL,  -- aporta latencia + estado
  umbral_ms   integer     CHECK (umbral_ms IS NULL OR umbral_ms >= 0), -- umbral propio del salto
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE servicio_componentes IS 'Saltos de una transacción; cada uno hereda latencia/estado de su recurso.';
CREATE INDEX IF NOT EXISTS idx_servicio_comp ON servicio_componentes(servicio_id, orden);

CREATE TRIGGER trg_servicios_updated BEFORE UPDATE ON servicios
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_servicio_comp_updated BEFORE UPDATE ON servicio_componentes
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
