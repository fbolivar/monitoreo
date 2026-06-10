// Configuración de entorno (dev). Copia/ajusta para producción.
// supabaseUrl/anonKey: panel Supabase -> Settings -> API.
// apiUrl: base de la API PHP/Laravel (FASE 2), incluye el prefijo /api.
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api',
  supabaseUrl: 'https://TU-PROYECTO.supabase.co',
  supabaseAnonKey: 'TU_ANON_KEY',
};
