import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import {
  DescubrimientoCandidato,
  DescubrimientoEscaneo,
  Paginated,
  Recurso,
  TipoRecurso,
} from './models';

@Injectable({ providedIn: 'root' })
export class DescubrimientoService {
  private api = inject(ApiService);

  listar(): Observable<Paginated<DescubrimientoEscaneo>> {
    return this.api.get<Paginated<DescubrimientoEscaneo>>('/descubrimiento', { per_page: 20 });
  }

  detalle(id: number): Observable<DescubrimientoEscaneo> {
    return this.api.get<DescubrimientoEscaneo>(`/descubrimiento/${id}`);
  }

  tipos(): Observable<TipoRecurso[]> {
    return this.api.get<TipoRecurso[]>('/descubrimiento/tipos');
  }

  escanear(body: {
    subred: string;
    snmp_version?: string;
    snmp_community?: string;
  }): Observable<DescubrimientoEscaneo> {
    return this.api.post<DescubrimientoEscaneo>('/descubrimiento', body);
  }

  eliminar(id: number): Observable<void> {
    return this.api.delete<void>(`/descubrimiento/${id}`);
  }

  agregar(
    candidatoId: number,
    body: {
      tipo_id: number;
      nombre: string;
      sitio_id?: number | null;
      intervalo_segundos?: number | null;
      secretos?: Record<string, unknown> | null;
    },
  ): Observable<Recurso> {
    return this.api.post<Recurso>(`/descubrimiento/candidatos/${candidatoId}/agregar`, body);
  }

  descartar(candidatoId: number): Observable<DescubrimientoCandidato> {
    return this.api.post<DescubrimientoCandidato>(
      `/descubrimiento/candidatos/${candidatoId}/descartar`,
      {},
    );
  }
}
