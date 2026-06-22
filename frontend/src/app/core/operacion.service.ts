import { HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import {
  Agente, Backup, Correlacion, Paginated, PoliticaCumplimiento, ResultadoCumplimiento,
  Runbook, RumResp, VmResp,
} from './models';

/** Servicios de las olas 2–5 (remediación, cumplimiento, agentes, VMs, RUM, AIOps). */
@Injectable({ providedIn: 'root' })
export class OperacionService {
  private api = inject(ApiService);

  // Runbooks (#5)
  runbooks(): Observable<Paginated<Runbook>> { return this.api.get('/runbooks', { per_page: 100 }); }
  runbook(id: number): Observable<Runbook> { return this.api.get(`/runbooks/${id}`); }
  crearRunbook(b: Partial<Runbook>): Observable<Runbook> { return this.api.post('/runbooks', b); }
  actualizarRunbook(id: number, b: Partial<Runbook>): Observable<Runbook> { return this.api.put(`/runbooks/${id}`, b); }
  eliminarRunbook(id: number): Observable<void> { return this.api.delete(`/runbooks/${id}`); }

  // Cumplimiento (#7)
  politicas(): Observable<Paginated<PoliticaCumplimiento>> { return this.api.get('/cumplimiento-politicas', { per_page: 100 }); }
  crearPolitica(b: Partial<PoliticaCumplimiento>): Observable<PoliticaCumplimiento> { return this.api.post('/cumplimiento-politicas', b); }
  actualizarPolitica(id: number, b: Partial<PoliticaCumplimiento>): Observable<PoliticaCumplimiento> { return this.api.put(`/cumplimiento-politicas/${id}`, b); }
  eliminarPolitica(id: number): Observable<void> { return this.api.delete(`/cumplimiento-politicas/${id}`); }
  resultadosCumplimiento(): Observable<Paginated<ResultadoCumplimiento>> { return this.api.get('/cumplimiento/resultados', { per_page: 100 }); }

  // Agentes (#8)
  agentes(): Observable<Paginated<Agente>> { return this.api.get('/agentes', { per_page: 100 }); }
  crearAgente(b: { nombre: string; recurso_id?: number | null }): Observable<{ agente: Agente; token: string }> { return this.api.post('/agentes', b); }
  eliminarAgente(id: number): Observable<void> { return this.api.delete(`/agentes/${id}`); }

  // Virtualización (#9)
  vms(recursoId: number): Observable<VmResp> { return this.api.get(`/recursos/${recursoId}/vms`); }

  // RUM (#13)
  rum(rango: '1h' | '24h' | '7d' = '24h'): Observable<RumResp> { return this.api.get('/rum', { rango }); }

  // Correlaciones (#14)
  correlaciones(): Observable<Paginated<Correlacion>> { return this.api.get('/correlaciones', { per_page: 30 }); }

  // Respaldos .pnnc (formato propio PNNC) — solo admin
  backups(): Observable<{ data: Backup[]; dir: string; formato: string }> { return this.api.get('/backups'); }
  generarBackup(b: { passphrase?: string; nota?: string }): Observable<{ data: Backup }> { return this.api.post('/backups/generar', b); }
  descargarBackup(id: string): Observable<HttpResponse<Blob>> { return this.api.descargar(`/backups/${id}/descargar`); }
  eliminarBackup(id: string): Observable<void> { return this.api.delete(`/backups/${encodeURIComponent(id)}`); }
}
