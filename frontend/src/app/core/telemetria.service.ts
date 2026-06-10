import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Chequeo, Incidencia, Metrica, Paginated } from './models';

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
}
