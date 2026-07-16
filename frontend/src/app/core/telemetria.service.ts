import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Chequeo, Incidencia, Metrica, NotaIncidencia, Paginated } from './models';

@Injectable({ providedIn: 'root' })
export class TelemetriaService {
  private api = inject(ApiService);

  chequeos(query: Record<string, unknown>): Observable<Paginated<Chequeo>> {
    return this.api.get<Paginated<Chequeo>>('/chequeos', query);
  }

  metricas(query: Record<string, unknown>): Observable<Paginated<Metrica>> {
    return this.api.get<Paginated<Metrica>>('/metricas', query);
  }

  incidencias(query?: Record<string, unknown>): Observable<Paginated<Incidencia>> {
    return this.api.get<Paginated<Incidencia>>('/incidencias', query);
  }

  reconocerIncidencia(id: number): Observable<Incidencia> {
    return this.api.post<Incidencia>(`/incidencias/${id}/reconocer`, {});
  }

  resolverIncidencia(id: number): Observable<Incidencia> {
    return this.api.post<Incidencia>(`/incidencias/${id}/resolver`, {});
  }

  // ── Bitácora de la incidencia (notas del operador) ──
  notasIncidencia(id: number): Observable<{ data: NotaIncidencia[] }> {
    return this.api.get<{ data: NotaIncidencia[] }>(`/incidencias/${id}/notas`);
  }

  agregarNotaIncidencia(id: number, nota: string): Observable<NotaIncidencia> {
    return this.api.post<NotaIncidencia>(`/incidencias/${id}/notas`, { nota });
  }
}
