import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { MapaPersonalizado, MapaResumen } from './models';

@Injectable({ providedIn: 'root' })
export class MapasService {
  private api = inject(ApiService);

  listar(): Observable<{ data: MapaResumen[] }> {
    return this.api.get<{ data: MapaResumen[] }>('/mapas');
  }
  obtener(id: number): Observable<MapaPersonalizado> {
    return this.api.get<MapaPersonalizado>(`/mapas/${id}`);
  }
  crear(b: Partial<MapaPersonalizado>): Observable<{ id: number }> {
    return this.api.post<{ id: number }>('/mapas', b);
  }
  actualizar(id: number, b: Partial<MapaPersonalizado>): Observable<{ id: number }> {
    return this.api.put<{ id: number }>(`/mapas/${id}`, b);
  }
  eliminar(id: number): Observable<void> {
    return this.api.delete<void>(`/mapas/${id}`);
  }
}
