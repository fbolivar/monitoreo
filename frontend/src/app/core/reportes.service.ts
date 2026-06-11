import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { ReporteDisponibilidad } from './models';

@Injectable({ providedIn: 'root' })
export class ReportesService {
  private api = inject(ApiService);

  disponibilidad(rango: '24h' | '7d' | '30d'): Observable<ReporteDisponibilidad> {
    return this.api.get<ReporteDisponibilidad>('/reportes/disponibilidad', { rango });
  }
}
