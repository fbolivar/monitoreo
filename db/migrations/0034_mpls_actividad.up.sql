-- Actividad de tráfico por subred de sede, vista desde el FortiGate.
-- La alimenta el job `refrescar_trafico_mpls` (muestrea las sesiones de la MPLS)
-- y la consulta el probe 'mpls' para decidir up/down sin depender de ICMP
-- (gateways de sede que enrutan pero no responden al ping).
CREATE TABLE IF NOT EXISTS mpls_actividad (
  subred        text PRIMARY KEY,                 -- p.ej. '192.168.3.0/25'
  ultimo_activo timestamptz NOT NULL DEFAULT now(),
  ips_activas   integer NOT NULL DEFAULT 0        -- nº de IPs con sesión en el último muestreo
);
