import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { Paginated, SyslogEvento } from './models';

@Injectable({ providedIn: 'root' })
export class SyslogService {
  private api = inject(ApiService);

  listar(query?: Record<string, unknown>): Observable<Paginated<SyslogEvento>> {
    return this.api.get<Paginated<SyslogEvento>>('/syslog', { per_page: 100, ...query });
  }
}
