import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Canal, LdapConfig, Mantenimiento, Paginated, Umbral } from './models';

/** CRUD de configuración: umbrales, mantenimientos y canales de notificación. */
@Injectable({ providedIn: 'root' })
export class ConfigService {
  private api = inject(ApiService);

  // ── Umbrales ──
  umbrales(query?: Record<string, unknown>): Observable<Paginated<Umbral>> {
    return this.api.get<Paginated<Umbral>>('/umbrales', { per_page: 200, ...query });
  }
  crearUmbral(b: Partial<Umbral>): Observable<Umbral> {
    return this.api.post<Umbral>('/umbrales', b);
  }
  actualizarUmbral(id: number, b: Partial<Umbral>): Observable<Umbral> {
    return this.api.put<Umbral>(`/umbrales/${id}`, b);
  }
  eliminarUmbral(id: number): Observable<void> {
    return this.api.delete<void>(`/umbrales/${id}`);
  }

  // ── Mantenimientos ──
  mantenimientos(query?: Record<string, unknown>): Observable<Paginated<Mantenimiento>> {
    return this.api.get<Paginated<Mantenimiento>>('/mantenimientos', { per_page: 200, ...query });
  }
  crearMantenimiento(b: Partial<Mantenimiento>): Observable<Mantenimiento> {
    return this.api.post<Mantenimiento>('/mantenimientos', b);
  }
  actualizarMantenimiento(id: number, b: Partial<Mantenimiento>): Observable<Mantenimiento> {
    return this.api.put<Mantenimiento>(`/mantenimientos/${id}`, b);
  }
  eliminarMantenimiento(id: number): Observable<void> {
    return this.api.delete<void>(`/mantenimientos/${id}`);
  }

  // ── Canales ──
  canales(query?: Record<string, unknown>): Observable<Paginated<Canal>> {
    return this.api.get<Paginated<Canal>>('/canales-notificacion', { per_page: 200, ...query });
  }
  crearCanal(b: Record<string, unknown>): Observable<Canal> {
    return this.api.post<Canal>('/canales-notificacion', b);
  }
  actualizarCanal(id: number, b: Record<string, unknown>): Observable<Canal> {
    return this.api.put<Canal>(`/canales-notificacion/${id}`, b);
  }
  eliminarCanal(id: number): Observable<void> {
    return this.api.delete<void>(`/canales-notificacion/${id}`);
  }

  // ── LDAP / SSO ──
  ldapObtener(): Observable<{ config: LdapConfig; disponible: boolean }> {
    return this.api.get<{ config: LdapConfig; disponible: boolean }>('/config/ldap');
  }
  ldapGuardar(b: LdapConfig): Observable<LdapConfig> {
    return this.api.put<LdapConfig>('/config/ldap', b);
  }
  ldapProbar(b: Record<string, unknown>): Observable<{ ok: boolean; mensaje: string }> {
    return this.api.post<{ ok: boolean; mensaje: string }>('/config/ldap/probar', b);
  }
}
