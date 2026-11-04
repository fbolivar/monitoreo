import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Chequeo, Incidencia, Metrica, NotaIncidencia, Paginated, RelevoTurno } from './models';

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

  // ── Consola de alarmas ──
  asignarIncidencia(id: number, body: { mi?: boolean; perfil_id?: string | null }): Observable<Incidencia> {
    return this.api.post<Incidencia>(`/incidencias/${id}/asignar`, body);
  }
  silenciarIncidencia(id: number, minutos: number): Observable<Incidencia> {
    return this.api.post<Incidencia>(`/incidencias/${id}/silenciar`, { minutos });
  }
  accionesIncidencias(ids: number[], accion: 'reconocer' | 'tomar' | 'silenciar' | 'resolver',
                      minutos?: number): Observable<{ afectadas: number; solicitadas: number }> {
    return this.api.post(`/incidencias/acciones`, { ids, accion, minutos });
  }

  // ── Relevo de turno (handover) ──
  relevos(limite = 20): Observable<{ data: RelevoTurno[] }> {
    return this.api.get<{ data: RelevoTurno[] }>('/relevos', { limite });
  }
  crearRelevo(resumen: string): Observable<RelevoTurno> {
    return this.api.post<RelevoTurno>('/relevos', { resumen });
  }
}
