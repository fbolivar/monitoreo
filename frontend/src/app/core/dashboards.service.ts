import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Dashboard } from './models';

@Injectable({ providedIn: 'root' })
export class DashboardsService {
  private api = inject(ApiService);

  listar(): Observable<{ data: Dashboard[] }> {
    return this.api.get<{ data: Dashboard[] }>('/dashboards');
  }
  crear(b: Partial<Dashboard>): Observable<{ id: number }> {
    return this.api.post<{ id: number }>('/dashboards', b);
  }
  actualizar(id: number, b: Partial<Dashboard>): Observable<{ id: number }> {
    return this.api.put<{ id: number }>(`/dashboards/${id}`, b);
  }
  eliminar(id: number): Observable<void> {
    return this.api.delete<void>(`/dashboards/${id}`);
  }
}
