// Configuración de entorno.
// apiUrl: base de la API. En el despliegue (nginx mismo origen) es '/api'.
//   Para `ng serve` local, usa un proxy (proxy.conf.json) o pon la URL completa.
// supabaseUrl/anonKey: panel Supabase -> Settings -> API (solo Auth; los datos
//   viven en el Postgres propio, no en Supabase).
// refreshMs: intervalo de refresco del dashboard por polling (opción B; sin
//   Supabase Realtime porque la BD es local).
export const environment = {
  production: false,
  apiUrl: '/api',
  refreshMs: 15000,
  supabaseUrl: 'https://TU-PROYECTO.supabase.co',
  supabaseAnonKey: 'TU_ANON_KEY',
};
