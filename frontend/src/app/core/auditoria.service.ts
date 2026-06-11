import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { AuditoriaEntrada, Paginated } from './models';

@Injectable({ providedIn: 'root' })
export class AuditoriaService {
  private api = inject(ApiService);

  listar(query?: Record<string, unknown>): Observable<Paginated<AuditoriaEntrada>> {
    return this.api.get<Paginated<AuditoriaEntrada>>('/auditoria', { per_page: 100, ...query });
  }
}
