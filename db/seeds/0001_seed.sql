-- =====================================================================
-- 0001_seed.sql — Datos de ejemplo
-- Requiere la variable psql :app_crypto_key (clave maestra de cifrado).
--   psql ... -v app_crypto_key="$APP_CRYPTO_KEY" -f 0001_seed.sql
-- Se ejecuta sobre una BD recién migrada (0001 + 0002).
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Catálogo: tipos de recurso
-- ---------------------------------------------------------------------
INSERT INTO tipos_recurso (codigo, nombre, descripcion, protocolo_default, icono) VALUES
  ('firewall',   'Firewall (FortiGate)',         'Cortafuegos perimetral FortiGate',          'snmp',     'shield'),
  ('servidor',   'Servidor (físico/virtual)',    'Servidores físicos y virtuales',            'snmp',     'server'),
  ('switch_lan', 'Switch de red (LAN)',          'Switches de acceso/distribución LAN',       'snmp',     'network'),
  ('nas',        'Almacenamiento NAS',           'Esquemas de almacenamiento NAS',            'snmp',     'database'),
  ('switch_san', 'Switch de fibra (SAN/FC)',     'Switches Fibre Channel para SAN',           'snmp',     'hard-drive'),
  ('ups',        'UPS (respaldo de energía)',    'Sistemas de alimentación ininterrumpida',   'snmp',     'battery'),
  ('starlink',   'Enlace satelital Starlink',    'Enlaces satelitales Starlink',              'starlink', 'satellite'),
  ('fibra_wan',  'Enlace de fibra óptica (WAN)', 'Enlaces WAN de fibra óptica',               'icmp',     'cable'),
  ('sitio_web',  'Sitio web',                    'Sitios web internos y públicos',            'https',    'globe');

-- ---------------------------------------------------------------------
-- Sitios
-- ---------------------------------------------------------------------
INSERT INTO sitios (codigo, nombre, direccion, ciudad, latitud, longitud, descripcion) VALUES
  ('SEDE-PPAL', 'Sede Principal',     'Calle 1 # 2-3',   'Bogotá',       4.710989, -74.072092, 'Sede administrativa principal'),
  ('DC-01',     'Datacenter Primario','Zona Franca',     'Bogotá',       4.701000, -74.146000, 'Centro de datos primario'),
  ('SUC-NORTE', 'Sucursal Norte',     'Av. Norte # 100', 'Bogotá',       4.760000, -74.045000, 'Sucursal zona norte'),
  ('SITIO-REM', 'Sitio Remoto',       'Vereda El Alto',  'Villavicencio', 4.142000, -73.626000, 'Sitio remoto enlazado por Starlink');

-- ---------------------------------------------------------------------
-- Perfiles de usuario (id uuid; en prod = auth.users.id de Supabase)
-- ---------------------------------------------------------------------
INSERT INTO perfiles (id, email, nombre, rol) VALUES
  ('00000000-0000-0000-0000-000000000001', 'admin@entidad.gov.co',    'Administrador TI', 'admin'),
  ('00000000-0000-0000-0000-000000000002', 'noc@entidad.gov.co',      'Operador NOC',     'operador'),
  ('00000000-0000-0000-0000-000000000003', 'gerencia@entidad.gov.co', 'Gerencia',         'viewer');

-- ---------------------------------------------------------------------
-- Recursos (2-3 por tipo). tipo_id/sitio_id resueltos por código.
-- Los secretos van cifrados con cifrar_secreto(jsonb, :app_crypto_key).
-- ---------------------------------------------------------------------

-- Helper inline: usamos subconsultas escalares para tipo y sitio.
-- FIREWALLS
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='firewall'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'FortiGate-DC-01', '10.0.0.1',
   '{"port":161,"snmp_version":"2c","oids":{"cpu":"1.3.6.1.4.1.12356.101.4.1.3.0","mem":"1.3.6.1.4.1.12356.101.4.1.4.0"}}'::jsonb,
   cifrar_secreto('{"snmp_community":"fgt-ro-2024"}'::jsonb, :'app_crypto_key'), 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='firewall'), (SELECT id FROM sitios WHERE codigo='SEDE-PPAL'),
   'FortiGate-Sede', '10.1.0.1',
   '{"port":161,"snmp_version":"2c"}'::jsonb,
   cifrar_secreto('{"snmp_community":"fgt-ro-2024"}'::jsonb, :'app_crypto_key'), 60);

-- SERVIDORES
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='servidor'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'SRV-APP-01', '10.0.1.10',
   '{"port":161,"snmp_version":"2c","oids":{"cpu":"1.3.6.1.4.1.2021.11.10.0"}}'::jsonb,
   cifrar_secreto('{"snmp_community":"srv-ro"}'::jsonb, :'app_crypto_key'), 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='servidor'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'SRV-DB-01', '10.0.1.11',
   '{"port":161,"snmp_version":"2c"}'::jsonb,
   cifrar_secreto('{"snmp_community":"srv-ro"}'::jsonb, :'app_crypto_key'), 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='servidor'), (SELECT id FROM sitios WHERE codigo='SEDE-PPAL'),
   'SRV-AD-01', '10.1.1.10',
   '{"port":161,"snmp_version":"3"}'::jsonb,
   cifrar_secreto('{"snmp_user":"monitor","snmp_auth":"authpass","snmp_priv":"privpass"}'::jsonb, :'app_crypto_key'), 120);

-- SWITCHES LAN
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='switch_lan'), (SELECT id FROM sitios WHERE codigo='SEDE-PPAL'),
   'SW-CORE-01', '10.1.0.2',
   '{"port":161,"snmp_version":"2c"}'::jsonb,
   cifrar_secreto('{"snmp_community":"sw-ro"}'::jsonb, :'app_crypto_key'), 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='switch_lan'), (SELECT id FROM sitios WHERE codigo='SUC-NORTE'),
   'SW-ACC-NORTE', '10.2.0.2',
   '{"port":161,"snmp_version":"2c"}'::jsonb,
   cifrar_secreto('{"snmp_community":"sw-ro"}'::jsonb, :'app_crypto_key'), 60);

-- NAS
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='nas'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'NAS-01', '10.0.2.20',
   '{"port":161,"snmp_version":"2c","oids":{"vol_used":"1.3.6.1.4.1.6574.3.1.1.0"}}'::jsonb,
   cifrar_secreto('{"snmp_community":"nas-ro"}'::jsonb, :'app_crypto_key'), 300),
  ((SELECT id FROM tipos_recurso WHERE codigo='nas'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'NAS-BACKUP', '10.0.2.21',
   '{"port":161,"snmp_version":"2c"}'::jsonb,
   cifrar_secreto('{"snmp_community":"nas-ro"}'::jsonb, :'app_crypto_key'), 300);

-- SWITCHES SAN (Fibre Channel)
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='switch_san'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'SAN-FC-01', '10.0.3.30',
   '{"port":161,"snmp_version":"2c"}'::jsonb,
   cifrar_secreto('{"snmp_community":"san-ro"}'::jsonb, :'app_crypto_key'), 120),
  ((SELECT id FROM tipos_recurso WHERE codigo='switch_san'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'SAN-FC-02', '10.0.3.31',
   '{"port":161,"snmp_version":"2c"}'::jsonb,
   cifrar_secreto('{"snmp_community":"san-ro"}'::jsonb, :'app_crypto_key'), 120);

-- UPS
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='ups'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'UPS-DC-01', '10.0.4.40',
   '{"port":161,"snmp_version":"1","oids":{"carga":"1.3.6.1.2.1.33.1.4.4.1.5.1","bateria":"1.3.6.1.2.1.33.1.2.4.0"}}'::jsonb,
   cifrar_secreto('{"snmp_community":"ups-ro"}'::jsonb, :'app_crypto_key'), 120),
  ((SELECT id FROM tipos_recurso WHERE codigo='ups'), (SELECT id FROM sitios WHERE codigo='SEDE-PPAL'),
   'UPS-SEDE-01', '10.1.4.40',
   '{"port":161,"snmp_version":"1"}'::jsonb,
   cifrar_secreto('{"snmp_community":"ups-ro"}'::jsonb, :'app_crypto_key'), 120);

-- STARLINK
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='starlink'), (SELECT id FROM sitios WHERE codigo='SITIO-REM'),
   'STARLINK-REMOTO', '192.168.100.1',
   '{"grpc_port":9200,"check":"dish_status"}'::jsonb,
   NULL, 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='starlink'), (SELECT id FROM sitios WHERE codigo='SUC-NORTE'),
   'STARLINK-NORTE', '192.168.101.1',
   '{"grpc_port":9200,"check":"dish_status"}'::jsonb,
   NULL, 60);

-- FIBRA WAN
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='fibra_wan'), (SELECT id FROM sitios WHERE codigo='SEDE-PPAL'),
   'WAN-FIBRA-ISP1', '8.8.8.8',
   '{"metodo":"icmp","reintentos":3,"timeout_ms":1000}'::jsonb,
   NULL, 30),
  ((SELECT id FROM tipos_recurso WHERE codigo='fibra_wan'), (SELECT id FROM sitios WHERE codigo='DC-01'),
   'WAN-FIBRA-ISP2', '1.1.1.1',
   '{"metodo":"icmp","reintentos":3,"timeout_ms":1000}'::jsonb,
   NULL, 30);

-- SITIOS WEB
INSERT INTO recursos (tipo_id, sitio_id, nombre, hostname, parametros, secretos, intervalo_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='sitio_web'), NULL,
   'Portal Público', 'https://www.entidad.gov.co',
   '{"http_path":"/","expected_status":200,"timeout_ms":5000,"match_text":"Bienvenido"}'::jsonb,
   NULL, 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='sitio_web'), NULL,
   'Intranet', 'https://intranet.entidad.local',
   '{"http_path":"/health","expected_status":200,"timeout_ms":5000}'::jsonb,
   cifrar_secreto('{"basic_auth_user":"probe","basic_auth_pass":"probe-pass"}'::jsonb, :'app_crypto_key'), 120),
  ((SELECT id FROM tipos_recurso WHERE codigo='sitio_web'), NULL,
   'API Ciudadano', 'https://api.entidad.gov.co',
   '{"http_path":"/v1/ping","expected_status":200,"timeout_ms":3000}'::jsonb,
   cifrar_secreto('{"api_key":"sk-probe-9f8e7d"}'::jsonb, :'app_crypto_key'), 60);

-- ---------------------------------------------------------------------
-- Umbrales por defecto (a nivel de tipo)
-- ---------------------------------------------------------------------
INSERT INTO umbrales (tipo_id, metrica, operador, valor_warning, valor_critical, duracion_segundos) VALUES
  ((SELECT id FROM tipos_recurso WHERE codigo='servidor'),  'cpu',     '>', 80, 95, 120),
  ((SELECT id FROM tipos_recurso WHERE codigo='servidor'),  'mem',     '>', 85, 95, 120),
  ((SELECT id FROM tipos_recurso WHERE codigo='firewall'),  'cpu',     '>', 75, 90, 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='nas'),       'vol_used','>', 80, 90, 0),
  ((SELECT id FROM tipos_recurso WHERE codigo='ups'),       'bateria', '<', 50, 20, 0),
  ((SELECT id FROM tipos_recurso WHERE codigo='starlink'),  'latency', '>', 150, 400, 60),
  ((SELECT id FROM tipos_recurso WHERE codigo='fibra_wan'), 'latency', '>', 80, 200, 30),
  ((SELECT id FROM tipos_recurso WHERE codigo='fibra_wan'), 'loss',    '>', 2, 10, 30),
  ((SELECT id FROM tipos_recurso WHERE codigo='sitio_web'), 'latency', '>', 1000, 3000, 0);

-- ---------------------------------------------------------------------
-- Canales de notificación
-- ---------------------------------------------------------------------
INSERT INTO canales_notificacion (tipo, nombre, config, secretos) VALUES
  ('email',   'Correo NOC',      '{"destinatarios":["noc@entidad.gov.co","admin@entidad.gov.co"]}'::jsonb, NULL),
  ('webhook', 'Webhook interno', '{"url":"https://hooks.entidad.local/alertas"}'::jsonb,
     cifrar_secreto('{"token":"whk-secret-123"}'::jsonb, :'app_crypto_key')),
  ('telegram','Telegram TI',     '{"chat_id":"-1001234567890"}'::jsonb,
     cifrar_secreto('{"bot_token":"123456:ABC-DEF"}'::jsonb, :'app_crypto_key'));

-- ---------------------------------------------------------------------
-- Datos de telemetría de ejemplo (chequeos + métricas) para 2 recursos
-- ---------------------------------------------------------------------
-- FortiGate-DC-01: 5 chequeos UP recientes con CPU/MEM
DO $$
DECLARE
  v_recurso bigint := (SELECT id FROM recursos WHERE nombre='FortiGate-DC-01');
  i integer;
  v_ts timestamptz;
BEGIN
  FOR i IN 0..5 LOOP
    v_ts := now() - make_interval(mins => i * 5);
    INSERT INTO chequeos (recurso_id, ts, estado, latencia_ms, detalle)
      VALUES (v_recurso, v_ts, 'up', 4 + i, jsonb_build_object('msg','snmp ok'));
    INSERT INTO metricas (recurso_id, metrica, valor, unidad, ts) VALUES
      (v_recurso, 'cpu', 30 + i * 2, '%', v_ts),
      (v_recurso, 'mem', 55 + i,     '%', v_ts);
  END LOOP;
  -- Actualiza estado cacheado
  UPDATE recursos SET estado_actual='up', ultimo_chequeo_at=now() WHERE id=v_recurso;
END $$;

-- WAN-FIBRA-ISP1: degradado con latencia alta -> incidencia abierta
DO $$
DECLARE
  v_recurso bigint := (SELECT id FROM recursos WHERE nombre='WAN-FIBRA-ISP1');
  v_chk     bigint;
BEGIN
  INSERT INTO metricas (recurso_id, metrica, valor, unidad, ts) VALUES
    (v_recurso, 'latency', 120, 'ms', now() - interval '2 min'),
    (v_recurso, 'latency', 180, 'ms', now() - interval '1 min'),
    (v_recurso, 'loss',    5,   '%',  now() - interval '1 min');

  INSERT INTO chequeos (recurso_id, ts, estado, latencia_ms, detalle)
    VALUES (v_recurso, now(), 'degraded', 180, '{"msg":"latencia/pérdida sobre umbral"}'::jsonb)
    RETURNING id INTO v_chk;

  UPDATE recursos SET estado_actual='degraded', ultimo_chequeo_at=now() WHERE id=v_recurso;

  INSERT INTO incidencias (recurso_id, estado, severidad, titulo, descripcion, chequeo_apertura_id)
    VALUES (v_recurso, 'abierta', 'warning',
            'Degradación de enlace WAN-FIBRA-ISP1',
            'Latencia 180ms y pérdida 5% sobre umbral.', v_chk);
END $$;

-- Ventana de mantenimiento programada para NAS-BACKUP (futura)
INSERT INTO mantenimientos (recurso_id, inicio, fin, motivo, creado_por)
VALUES (
  (SELECT id FROM recursos WHERE nombre='NAS-BACKUP'),
  now() + interval '1 day',
  now() + interval '1 day 2 hours',
  'Actualización de firmware',
  '00000000-0000-0000-0000-000000000001'
);

-- Genera el rollup horario de lo insertado (demostración)
SELECT fn_rollup_metricas_horario(date_trunc('hour', now() - interval '1 hour'), now());

COMMIT;
