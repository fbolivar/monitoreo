import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Paginated, SyslogEvento, SyslogRegla } from './models';

@Injectable({ providedIn: 'root' })
export class SyslogService {
  private api = inject(ApiService);

  listar(query?: Record<string, unknown>): Observable<Paginated<SyslogEvento>> {
    return this.api.get<Paginated<SyslogEvento>>('/syslog', { per_page: 100, ...query });
  }

  // ── Reglas patrón→incidencia ──
  reglas(): Observable<{ data: SyslogRegla[] }> {
    return this.api.get<{ data: SyslogRegla[] }>('/syslog-reglas');
  }
  crearRegla(b: SyslogRegla): Observable<{ id: number }> {
    return this.api.post<{ id: number }>('/syslog-reglas', b);
  }
  actualizarRegla(id: number, b: SyslogRegla): Observable<{ id: number }> {
    return this.api.put<{ id: number }>(`/syslog-reglas/${id}`, b);
  }
  eliminarRegla(id: number): Observable<void> {
    return this.api.delete<void>(`/syslog-reglas/${id}`);
  }
}
