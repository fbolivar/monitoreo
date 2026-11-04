-- =====================================================================
-- 0045_consola_alarmas.up.sql
-- Consola de alarmas operativa (NOC) + relevo de turno.
--  1) incidencias.asignado_a    -> operador dueño de la alarma (quién la atiende).
--  2) incidencias.silenciado_hasta -> "snooze": la estoy trabajando, no me escales
--     ni me re-notifiques hasta esta hora (sin resolverla).
--  3) relevos_turno -> bitácora de entrega de turno: el operador saliente deja el
--     estado (pendientes, en curso) para el entrante. Es la memoria entre turnos 24x7.
-- =====================================================================
BEGIN;

ALTER TABLE incidencias
  ADD COLUMN IF NOT EXISTS asignado_a       uuid REFERENCES perfiles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS silenciado_hasta timestamptz;

COMMENT ON COLUMN incidencias.asignado_a       IS 'Operador que atiende la alarma (NULL = sin asignar).';
COMMENT ON COLUMN incidencias.silenciado_hasta IS 'Snooze: suprime escalamiento/re-notificación hasta esta hora.';

CREATE INDEX IF NOT EXISTS ix_incidencias_asignado ON incidencias (asignado_a) WHERE estado <> 'resuelta';

CREATE TABLE IF NOT EXISTS relevos_turno (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  perfil_id   uuid        REFERENCES perfiles(id) ON DELETE SET NULL,
  actor_email text        NOT NULL,            -- autoría en texto (sobrevive al borrado del perfil)
  resumen     text        NOT NULL,            -- qué queda pendiente / en curso para el siguiente turno
  creado_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_relevos_turno_ts ON relevos_turno (creado_at DESC);
COMMENT ON TABLE relevos_turno IS 'Entrega de turno del NOC: estado que el operador saliente deja al entrante.';

-- Dueño = rol de la app y lectura para Grafana (defensivo si se aplica como 'postgres').
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitoreo') THEN
    EXECUTE 'ALTER TABLE relevos_turno OWNER TO monitoreo';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    EXECUTE 'GRANT SELECT ON relevos_turno TO grafana_ro';
  END IF;
END $$;

COMMIT;
