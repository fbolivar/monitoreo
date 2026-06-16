-- =====================================================================
-- 0017_reportes_programados.up.sql
-- Reportes de disponibilidad/SLA programados: el worker los genera (PDF/CSV) y
-- los envía por correo (canal email) según su periodicidad. Cierra el ciclo de
-- "informe a gerencia" sin intervención manual.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS reportes_programados (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre          text        NOT NULL,
  periodo         text        NOT NULL DEFAULT 'mensual'        -- cada cuánto se envía
                    CHECK (periodo IN ('diario','semanal','mensual')),
  rango           text        NOT NULL DEFAULT '30d'            -- ventana de datos del informe
                    CHECK (rango IN ('24h','7d','30d')),
  destinatarios   text        NOT NULL,                         -- correos separados por coma
  formato         text        NOT NULL DEFAULT 'pdf'
                    CHECK (formato IN ('pdf','csv')),
  activo          boolean     NOT NULL DEFAULT true,
  ultimo_envio_at timestamptz,                                  -- para no reenviar dentro del periodo
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE reportes_programados IS 'Informes de SLA/disponibilidad enviados por correo según periodicidad.';

CREATE TRIGGER trg_reportes_programados_updated BEFORE UPDATE ON reportes_programados
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
