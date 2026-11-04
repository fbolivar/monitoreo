-- =====================================================================
-- 0046_oncall_escalado.up.sql
-- On-call / escalado multinivel (NOC P0-2).
--  * turnos_oncall + turno_participantes: quién está de guardia (rotación por N días).
--  * politicas_escalado + escalado_niveles: niveles ("si nadie reconoce en X min,
--    avisa a Y; si sigue sin reconocer en Z min, sube al siguiente"). El destino de
--    un nivel puede ser un CANAL (grupo), un TURNO (el de guardia) o un USUARIO.
--  * incidencias.nivel_escalado: hasta qué nivel se ha escalado (anti-repetición).
-- Si no hay políticas activas, el worker mantiene el escalado simple por ESCALATION_MIN.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS turnos_oncall (
  id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre        text        NOT NULL,
  activo        boolean     NOT NULL DEFAULT true,
  rotacion_dias integer     NOT NULL DEFAULT 7 CHECK (rotacion_dias >= 1),
  inicio_at     timestamptz NOT NULL DEFAULT now(),   -- ancla de la rotación
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS turno_participantes (
  id        bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  turno_id  bigint   NOT NULL REFERENCES turnos_oncall(id) ON DELETE CASCADE,
  orden     smallint NOT NULL,                         -- posición en la rotación (0..n-1)
  perfil_id uuid     NOT NULL REFERENCES perfiles(id) ON DELETE CASCADE,
  UNIQUE (turno_id, orden)
);

CREATE TABLE IF NOT EXISTS politicas_escalado (
  id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre        text        NOT NULL,
  activo        boolean     NOT NULL DEFAULT true,
  severidad_min text        NOT NULL DEFAULT 'warning'
                  CHECK (severidad_min IN ('info','warning','critical')),
  descripcion   text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escalado_niveles (
  id          bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  politica_id bigint   NOT NULL REFERENCES politicas_escalado(id) ON DELETE CASCADE,
  orden       smallint NOT NULL,                        -- 1,2,3…
  espera_min  integer  NOT NULL CHECK (espera_min >= 0),-- minutos desde apertura para disparar este nivel
  destino_tipo text    NOT NULL CHECK (destino_tipo IN ('canal','turno','usuario')),
  canal_id    bigint   REFERENCES canales_notificacion(id) ON DELETE CASCADE,
  turno_id    bigint   REFERENCES turnos_oncall(id) ON DELETE CASCADE,
  perfil_id   uuid     REFERENCES perfiles(id) ON DELETE CASCADE,
  UNIQUE (politica_id, orden)
);
CREATE INDEX IF NOT EXISTS ix_escalado_niveles_pol ON escalado_niveles (politica_id, orden);

ALTER TABLE incidencias
  ADD COLUMN IF NOT EXISTS nivel_escalado smallint NOT NULL DEFAULT 0;

COMMENT ON TABLE turnos_oncall       IS 'Turnos de guardia: rotación de N días sobre una lista de participantes.';
COMMENT ON TABLE politicas_escalado  IS 'Políticas de escalado multinivel por severidad.';
COMMENT ON TABLE escalado_niveles    IS 'Niveles de una política: a los X min sin reconocer, avisa al destino.';
COMMENT ON COLUMN incidencias.nivel_escalado IS 'Último nivel de escalado alcanzado (0 = ninguno).';

-- Dueño/grant para el rol de la app (defensivo si se aplica como 'postgres').
DO $$
DECLARE t text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitoreo') THEN
    FOREACH t IN ARRAY ARRAY['turnos_oncall','turno_participantes','politicas_escalado','escalado_niveles']
    LOOP EXECUTE format('ALTER TABLE %I OWNER TO monitoreo', t); END LOOP;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    FOREACH t IN ARRAY ARRAY['turnos_oncall','turno_participantes','politicas_escalado','escalado_niveles']
    LOOP EXECUTE format('GRANT SELECT ON %I TO grafana_ro', t); END LOOP;
  END IF;
END $$;

COMMIT;
