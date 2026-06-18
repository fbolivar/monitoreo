-- =====================================================================
-- 0029_push.up.sql — Notificaciones push (PWA / Web Push) (#11)
-- Suscripciones del navegador (Web Push API, VAPID). El worker envía push a
-- estas suscripciones al abrir/cerrar incidencias (pywebpush).
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS push_suscripciones (
  id          bigserial PRIMARY KEY,
  perfil_id   uuid REFERENCES perfiles(id) ON DELETE CASCADE,
  endpoint    text NOT NULL UNIQUE,
  p256dh      text NOT NULL,
  auth        text NOT NULL,
  user_agent  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_push_perfil ON push_suscripciones(perfil_id);

COMMENT ON TABLE push_suscripciones IS 'Suscripciones Web Push (PWA) para notificaciones al navegador/móvil.';

COMMIT;
