import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Servicio, ServicioAnalisis } from './models';

/** Observabilidad de servicios: transacciones y su análisis de correlación. */
@Injectable({ providedIn: 'root' })
export class ServiciosService {
  private api = inject(ApiService);

  /** Lista con resumen de análisis (estado, experiencia, cuello) por servicio. */
  lista(): Observable<ServicioAnalisis[]> {
    return this.api.get<ServicioAnalisis[]>('/servicios');
  }
  /** Servicio con sus componentes (para editar). */
  obtener(id: number): Observable<Servicio> {
    return this.api.get<Servicio>(`/servicios/${id}`);
  }
  /** Análisis de correlación completo (componentes, cuello, causa, impacto). */
  analisis(id: number): Observable<ServicioAnalisis> {
    return this.api.get<ServicioAnalisis>(`/servicios/${id}/analisis`);
  }
  crear(b: Record<string, unknown>): Observable<Servicio> {
    return this.api.post<Servicio>('/servicios', b);
  }
  actualizar(id: number, b: Record<string, unknown>): Observable<Servicio> {
    return this.api.put<Servicio>(`/servicios/${id}`, b);
  }
  eliminar(id: number): Observable<void> {
    return this.api.delete<void>(`/servicios/${id}`);
  }
}
