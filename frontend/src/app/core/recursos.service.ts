import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Baseline, Interfaz, MuestraInterfaz, Paginated, Recurso, Respaldo, RespaldoDetalle, Sitio, TipoRecurso } from './models';

@Injectable({ providedIn: 'root' })
export class RecursosService {
  private api = inject(ApiService);

  listar(query?: Record<string, unknown>): Observable<Paginated<Recurso>> {
    return this.api.get<Paginated<Recurso>>('/recursos', { per_page: 200, ...query });
  }
  obtener(id: number): Observable<Recurso> {
    return this.api.get<Recurso>(`/recursos/${id}`);
  }
  crear(body: Partial<Recurso>): Observable<Recurso> {
    return this.api.post<Recurso>('/recursos', body);
  }
  actualizar(id: number, body: Partial<Recurso>): Observable<Recurso> {
    return this.api.put<Recurso>(`/recursos/${id}`, body);
  }
  eliminar(id: number): Observable<void> {
    return this.api.delete<void>(`/recursos/${id}`);
  }

  interfaces(id: number): Observable<Interfaz[]> {
    return this.api.get<Interfaz[]>(`/recursos/${id}/interfaces`);
  }
  interfazMonitorear(id: number, ifIndex: number, monitorear: boolean): Observable<unknown> {
    return this.api.put(`/recursos/${id}/interfaces/${ifIndex}`, { monitorear });
  }
  interfazHistorico(id: number, ifIndex: number, rango: '1h' | '24h' | '7d'): Observable<MuestraInterfaz[]> {
    return this.api.get<MuestraInterfaz[]>(`/recursos/${id}/interfaces/${ifIndex}/historico`, { rango });
  }

  baselines(id: number): Observable<Baseline[]> {
    return this.api.get<Baseline[]>(`/recursos/${id}/baselines`);
  }

  respaldos(id: number): Observable<Respaldo[]> {
    return this.api.get<Respaldo[]>(`/recursos/${id}/respaldos`);
  }
  respaldoContenido(id: number, respaldoId: number): Observable<RespaldoDetalle> {
    return this.api.get<RespaldoDetalle>(`/recursos/${id}/respaldos/${respaldoId}`);
  }

  tipos(): Observable<Paginated<TipoRecurso>> {
    return this.api.get<Paginated<TipoRecurso>>('/tipos-recurso', { per_page: 100 });
  }
  sitios(): Observable<Paginated<Sitio>> {
    return this.api.get<Paginated<Sitio>>('/sitios', { per_page: 100 });
  }
}
