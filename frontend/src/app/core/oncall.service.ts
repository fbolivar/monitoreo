import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { PoliticaEscalado, TurnoOncall } from './models';

@Injectable({ providedIn: 'root' })
export class OncallService {
  private api = inject(ApiService);

  turnos(): Observable<{ data: TurnoOncall[] }> {
    return this.api.get<{ data: TurnoOncall[] }>('/turnos-oncall');
  }
  crearTurno(b: Record<string, unknown>): Observable<{ id: number }> {
    return this.api.post<{ id: number }>('/turnos-oncall', b);
  }
  actualizarTurno(id: number, b: Record<string, unknown>): Observable<{ id: number }> {
    return this.api.put<{ id: number }>(`/turnos-oncall/${id}`, b);
  }
  eliminarTurno(id: number): Observable<void> {
    return this.api.delete<void>(`/turnos-oncall/${id}`);
  }

  politicas(): Observable<{ data: PoliticaEscalado[] }> {
    return this.api.get<{ data: PoliticaEscalado[] }>('/politicas-escalado');
  }
  crearPolitica(b: Record<string, unknown>): Observable<{ id: number }> {
    return this.api.post<{ id: number }>('/politicas-escalado', b);
  }
  actualizarPolitica(id: number, b: Record<string, unknown>): Observable<{ id: number }> {
    return this.api.put<{ id: number }>(`/politicas-escalado/${id}`, b);
  }
  eliminarPolitica(id: number): Observable<void> {
    return this.api.delete<void>(`/politicas-escalado/${id}`);
  }
}
