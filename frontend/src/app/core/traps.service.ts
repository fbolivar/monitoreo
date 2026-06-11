import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Paginated, Trap } from './models';

@Injectable({ providedIn: 'root' })
export class TrapsService {
  private api = inject(ApiService);

  listar(query?: Record<string, unknown>): Observable<Paginated<Trap>> {
    return this.api.get<Paginated<Trap>>('/traps', { per_page: 100, ...query });
  }
}
