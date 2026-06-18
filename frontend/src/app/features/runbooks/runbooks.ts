import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';
import { Runbook } from '../../core/models';
import { OperacionService } from '../../core/operacion.service';

/** Auto-remediación / runbooks (#5): acciones automáticas al abrir incidencias. */
@Component({
  selector: 'app-runbooks',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="head">
      <h1>Runbooks <span class="text-dim">· auto-remediación</span></h1>
      @if (auth.puedeEditar()) { <button class="btn" (click)="nuevo()">+ Nuevo</button> }
    </div>
    <p class="intro text-dim">Acciones que se ejecutan automáticamente al abrir una incidencia que
      coincide con los disparadores (webhook a un orquestador o comando SSH al equipo).</p>

    @if (cargando()) { <p class="text-dim">Cargando…</p> }
    @else {
      <table class="tabla">
        <thead><tr><th>Nombre</th><th>Disparador</th><th>Acción</th><th>Activo</th><th></th></tr></thead>
        <tbody>
          @for (r of lista(); track r.id) {
            <tr>
              <td><b>{{ r.nombre }}</b><br><span class="text-dim">{{ r.descripcion }}</span></td>
              <td class="text-dim">
                {{ r.trigger_severidad || 'cualquier sev.' }}
                @if (r.trigger_match) { · "{{ r.trigger_match }}" }
              </td>
              <td><span class="chip">{{ r.accion?.tipo }}</span></td>
              <td>{{ r.activo ? 'Sí' : 'No' }}</td>
              <td class="acc">
                @if (auth.puedeEditar()) {
                  <button class="lnk" (click)="editar(r)">Editar</button>
                  <button class="lnk del" (click)="eliminar(r)">Eliminar</button>
                }
              </td>
            </tr>
          }
          @if (lista().length === 0) { <tr><td colspan="5" class="text-dim">Sin runbooks.</td></tr> }
        </tbody>
      </table>
    }

    @if (edit(); as e) {
      <div class="modal" (click)="edit.set(null)">
        <div class="card" (click)="$event.stopPropagation()">
          <h2>{{ e.id ? 'Editar' : 'Nuevo' }} runbook</h2>
          <label>Nombre <input [(ngModel)]="e.nombre"></label>
          <label>Descripción <input [(ngModel)]="e.descripcion"></label>
          <div class="row">
            <label>Severidad mínima
              <select [(ngModel)]="e.trigger_severidad">
                <option [ngValue]="null">cualquiera</option>
                <option value="warning">warning</option>
                <option value="critical">critical</option>
              </select>
            </label>
            <label>Coincide título <input [(ngModel)]="e.trigger_match" placeholder="ej. puerto"></label>
          </div>
          <label>Tipo de acción
            <select [(ngModel)]="accTipo">
              <option value="webhook">webhook</option>
              <option value="ssh">ssh (comando)</option>
            </select>
          </label>
          @if (accTipo === 'webhook') {
            <label>URL <input [(ngModel)]="accUrl" placeholder="https://orquestador/hook"></label>
            <label>Token (secreto) <input [(ngModel)]="secToken" type="password"></label>
          } @else {
            <label>Host <input [(ngModel)]="accHost" placeholder="vacío = usa el hostname del recurso"></label>
            <label>Comando <input [(ngModel)]="accComando" placeholder="ej. systemctl restart nginx"></label>
            <div class="row">
              <label>Usuario SSH <input [(ngModel)]="secUser"></label>
              <label>Clave SSH <input [(ngModel)]="secPass" type="password"></label>
            </div>
          }
          <label class="chk"><input type="checkbox" [(ngModel)]="e.activo"> Activo</label>
          <div class="actions">
            <button class="btn" (click)="guardar()">Guardar</button>
            <button class="lnk" (click)="edit.set(null)">Cancelar</button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .head { display: flex; align-items: center; gap: 14px; margin: 8px 0 10px; }
    h1 { font-size: 18px; margin: 0; }
    .intro { font-size: 12.5px; margin: 0 0 12px; max-width: 760px; }
    .tabla { width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; border: 1px solid var(--border); border-radius: var(--radius); }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    .chip { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: #eef3f0; font-weight: 600; }
    .acc { white-space: nowrap; }
    .lnk { border: 0; background: none; color: var(--brand, #1b6b3a); cursor: pointer; font-size: 12px; }
    .lnk.del { color: #c0392b; }
    .btn { background: var(--brand, #1b6b3a); color: #fff; border: 0; border-radius: 8px; padding: 7px 14px; cursor: pointer; font-weight: 600; }
    .modal { position: fixed; inset: 0; background: #0006; display: flex; align-items: center; justify-content: center; z-index: 50; }
    .modal .card { background: #fff; border-radius: 12px; padding: 18px 20px; width: 460px; max-width: 92vw; max-height: 90vh; overflow: auto; }
    .modal h2 { font-size: 15px; margin: 0 0 12px; }
    .modal label { display: flex; flex-direction: column; font-size: 12px; gap: 3px; margin-bottom: 9px; }
    .modal input, .modal select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 7px; font: inherit; }
    .modal .row { display: flex; gap: 10px; } .modal .row label { flex: 1; }
    .modal .chk { flex-direction: row; align-items: center; }
    .actions { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
  `],
})
export class Runbooks implements OnInit {
  private svc = inject(OperacionService);
  auth = inject(AuthService);

  lista = signal<Runbook[]>([]);
  cargando = signal(true);
  edit = signal<Partial<Runbook> | null>(null);

  accTipo = 'webhook'; accUrl = ''; accHost = ''; accComando = '';
  secToken = ''; secUser = ''; secPass = '';

  ngOnInit(): void { this.cargar(); }
  cargar(): void {
    this.cargando.set(true);
    this.svc.runbooks().subscribe({ next: (p) => { this.lista.set(p.data); this.cargando.set(false); }, error: () => this.cargando.set(false) });
  }

  nuevo(): void {
    this.accTipo = 'webhook'; this.accUrl = this.accHost = this.accComando = '';
    this.secToken = this.secUser = this.secPass = '';
    this.edit.set({ nombre: '', activo: true, trigger_severidad: null });
  }
  editar(r: Runbook): void {
    this.accTipo = r.accion?.tipo || 'webhook';
    this.accUrl = (r.accion as any)?.url || ''; this.accHost = (r.accion as any)?.host || '';
    this.accComando = (r.accion as any)?.comando || '';
    this.secToken = this.secUser = this.secPass = '';
    this.edit.set({ ...r });
  }

  guardar(): void {
    const e = this.edit(); if (!e) return;
    const accion: any = { tipo: this.accTipo };
    const secretos: any = {};
    if (this.accTipo === 'webhook') { accion.url = this.accUrl; if (this.secToken) secretos.token = this.secToken; }
    else { if (this.accHost) accion.host = this.accHost; accion.comando = this.accComando;
           if (this.secUser) secretos.ssh_user = this.secUser; if (this.secPass) secretos.ssh_password = this.secPass; }
    const body: Partial<Runbook> = {
      nombre: e.nombre, descripcion: e.descripcion, activo: e.activo,
      trigger_severidad: e.trigger_severidad || null, trigger_match: e.trigger_match || null,
      accion,
    };
    if (Object.keys(secretos).length) (body as any).secretos = secretos;
    const obs = e.id ? this.svc.actualizarRunbook(e.id, body) : this.svc.crearRunbook(body);
    obs.subscribe({ next: () => { this.edit.set(null); this.cargar(); } });
  }

  eliminar(r: Runbook): void {
    if (!confirm(`¿Eliminar runbook "${r.nombre}"?`)) return;
    this.svc.eliminarRunbook(r.id).subscribe({ next: () => this.cargar() });
  }
}
