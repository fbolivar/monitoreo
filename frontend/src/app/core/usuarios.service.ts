import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Paginated, Perfil } from './models';

/** Gestión de usuarios (perfiles) — solo admin. */
@Injectable({ providedIn: 'root' })
export class UsuariosService {
  private api = inject(ApiService);

  listar(query?: Record<string, unknown>): Observable<Paginated<Perfil>> {
    return this.api.get<Paginated<Perfil>>('/usuarios', { per_page: 200, ...query });
  }
  crear(body: Record<string, unknown>): Observable<Perfil> {
    return this.api.post<Perfil>('/usuarios', body);
  }
  actualizar(id: string, body: Record<string, unknown>): Observable<Perfil> {
    return this.api.put<Perfil>(`/usuarios/${id}`, body);
  }
  eliminar(id: string): Observable<void> {
    return this.api.delete<void>(`/usuarios/${id}`);
  }

  /** Alcance del usuario: sitios a los que puede acceder ([] = toda la entidad). */
  sitiosDe(id: string): Observable<{ data: number[] }> {
    return this.api.get<{ data: number[] }>(`/usuarios/${id}/sitios`);
  }

  asignarSitios(id: string, sitios: number[]): Observable<{ data: number[] }> {
    return this.api.put<{ data: number[] }>(`/usuarios/${id}/sitios`, { sitios });
  }
}
