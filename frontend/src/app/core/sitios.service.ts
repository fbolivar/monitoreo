import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Paginated, Sitio } from './models';

/** CRUD de sitios (ubicaciones). Escritura gated a admin/operador en la API. */
@Injectable({ providedIn: 'root' })
export class SitiosService {
  private api = inject(ApiService);

  listar(query?: Record<string, unknown>): Observable<Paginated<Sitio>> {
    return this.api.get<Paginated<Sitio>>('/sitios', { per_page: 200, ...query });
  }
  crear(body: Partial<Sitio>): Observable<Sitio> {
    return this.api.post<Sitio>('/sitios', body);
  }
  actualizar(id: number, body: Partial<Sitio>): Observable<Sitio> {
    return this.api.put<Sitio>(`/sitios/${id}`, body);
  }
  eliminar(id: number): Observable<void> {
    return this.api.delete<void>(`/sitios/${id}`);
  }
}
