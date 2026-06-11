// Modelos compartidos (espejo de las respuestas JSON de la API PHP).

export type Estado = 'up' | 'degraded' | 'down' | 'unknown' | 'maintenance';
export type Severidad = 'info' | 'warning' | 'critical';
export type EstadoIncidencia = 'abierta' | 'reconocida' | 'resuelta';
export type Rol = 'admin' | 'operador' | 'viewer';

export interface TipoRecurso {
  id: number;
  codigo: string;
  nombre: string;
}

export interface Sitio {
  id: number;
  codigo: string;
  nombre: string;
  direccion?: string | null;
  ciudad?: string | null;
  latitud?: number | null;
  longitud?: number | null;
  descripcion?: string | null;
  activo?: boolean;
}

export interface Recurso {
  id: number;
  nombre: string;
  hostname?: string | null;
  estado_actual: Estado;
  tipo_id: number;
  sitio_id?: number | null;
  intervalo_segundos: number;
  activo: boolean;
  ultimo_chequeo_at?: string | null;
  parametros?: Record<string, unknown>;
  tipo?: TipoRecurso;
  sitio?: Sitio;
  tiene_secretos?: boolean;
}

export interface Chequeo {
  id: number;
  recurso_id: number;
  ts: string;
  estado: Estado;
  latencia_ms?: number | null;
  detalle?: Record<string, unknown>;
}

export interface Metrica {
  recurso_id: number;
  metrica: string;
  valor: number;
  unidad?: string | null;
  ts: string;
}

export interface Incidencia {
  id: number;
  recurso_id: number;
  estado: EstadoIncidencia;
  severidad: Severidad;
  titulo: string;
  descripcion?: string | null;
  abierta_at: string;
  reconocida_at?: string | null;
  resuelta_at?: string | null;
  recurso?: { id: number; nombre: string };
}

export interface Interfaz {
  recurso_id: number;
  if_index: number;
  if_name: string;
  admin_estado: string;       // up | down
  oper_estado: string;        // up | down
  speed_mbps?: number | null;
  in_mbps?: number | null;
  out_mbps?: number | null;
  util_in?: number | null;
  util_out?: number | null;
  in_err?: number | null;
  out_err?: number | null;
  ts: string;
}

export interface Perfil {
  id: string;
  email: string;
  nombre?: string | null;
  rol: Rol;
  activo: boolean;
}

export interface Umbral {
  id: number;
  recurso_id?: number | null;
  tipo_id?: number | null;
  metrica: string;
  operador: string;
  valor_warning?: number | null;
  valor_critical?: number | null;
  duracion_segundos: number;
  activo: boolean;
}

export interface Mantenimiento {
  id: number;
  recurso_id?: number | null;
  sitio_id?: number | null;
  inicio: string;
  fin: string;
  motivo: string;
  recurso?: { id: number; nombre: string };
  sitio?: { id: number; nombre: string };
}

export interface Canal {
  id: number;
  tipo: string;
  nombre: string;
  config?: Record<string, unknown>;
  activo: boolean;
  tiene_secretos?: boolean;
}

export const OPERADORES = ['>', '>=', '<', '<=', '==', '!='];
export const TIPOS_CANAL = ['email', 'sms', 'webhook', 'slack', 'telegram'];
export const ROLES: Rol[] = ['admin', 'operador', 'viewer'];

// Paginador de Laravel.
export interface Paginated<T> {
  data: T[];
  current_page: number;
  last_page: number;
  per_page: number;
  total: number;
}

export const ESTADOS: Estado[] = ['up', 'degraded', 'down', 'unknown', 'maintenance'];

export const ESTADO_LABEL: Record<Estado, string> = {
  up: 'Operativo',
  degraded: 'Degradado',
  down: 'Caído',
  unknown: 'Desconocido',
  maintenance: 'Mantenimiento',
};
