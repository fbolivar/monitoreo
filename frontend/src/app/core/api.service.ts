import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/** Wrapper HTTP sobre la API PHP. El token JWT lo añade authInterceptor. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  private params(query?: Record<string, unknown>): HttpParams {
    let p = new HttpParams();
    if (query) {
      for (const [k, v] of Object.entries(query)) {
        if (v !== undefined && v !== null && v !== '') {
          p = p.set(k, String(v));
        }
      }
    }
    return p;
  }

  get<T>(path: string, query?: Record<string, unknown>): Observable<T> {
    return this.http.get<T>(`${this.base}${path}`, { params: this.params(query) });
  }

  post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<T>(`${this.base}${path}`, body);
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<T>(`${this.base}${path}`, body);
  }

  delete<T>(path: string): Observable<T> {
    return this.http.delete<T>(`${this.base}${path}`);
  }

  /** Descarga un archivo (con el JWT del interceptor). Devuelve la respuesta con headers. */
  descargar(path: string, query?: Record<string, unknown>): Observable<HttpResponse<Blob>> {
    return this.http.get(`${this.base}${path}`, {
      params: this.params(query), responseType: 'blob', observe: 'response',
    });
  }
}
