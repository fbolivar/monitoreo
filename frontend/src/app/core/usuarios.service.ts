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
}
