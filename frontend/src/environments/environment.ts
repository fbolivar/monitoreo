// Configuración de entorno.
// apiUrl: base de la API. En el despliegue (nginx mismo origen) es '/api'.
//   Para `ng serve` local, usa un proxy (proxy.conf.json) o pon la URL completa.
// refreshMs: intervalo de refresco del dashboard por polling.
// Autenticación LOCAL contra la API (sin Supabase).
export const environment = {
  production: false,
  apiUrl: '/api',
  refreshMs: 15000,
};
