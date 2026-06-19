import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Agente } from '../../core/models';
import { OperacionService } from '../../core/operacion.service';
import { fecha, hace } from '../../shared/tiempo';

/** Agentes ligeros (#8): alta (token único) + estado. Solo admin. */
@Component({
  selector: 'app-agentes',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="head"><h1>Agentes ligeros</h1><button class="btn" (click)="form.set(true)">+ Nuevo agente</button></div>
    <p class="intro text-dim">Telemetría «desde dentro» del SO (procesos, servicios, disco por volumen).
      Crea un agente, copia su token y despliega <code>agent/simon_agent.py</code> en el host
      (variable <code>SIMON_TOKEN</code>) con una tarea cada minuto.</p>

    @if (form()) {
      <div class="form">
        <input [(ngModel)]="fNombre" placeholder="Nombre (ej. PNNCSRVNCFHV2)">
        <input [(ngModel)]="fRecurso" type="number" placeholder="ID recurso (opcional)">
        <button class="btn" (click)="crear()">Crear</button>
        <button class="lnk" (click)="form.set(false)">Cancelar</button>
      </div>
    }
    @if (token(); as t) {
      <div class="token">Token (cópialo ahora, no se vuelve a mostrar):<br><code>{{ t }}</code></div>
    }

    <table class="tabla">
      <thead><tr><th>Nombre</th><th>Host</th><th>SO</th><th>Recurso</th><th>Último reporte</th><th></th></tr></thead>
      <tbody>
        @for (a of lista(); track a.id) {
          <tr><td><b>{{ a.nombre }}</b></td><td class="text-dim">{{ a.hostname || '—' }}</td>
            <td class="text-dim">{{ a.so || '—' }}</td><td>{{ a.recurso_id || '—' }}</td>
            <td [class.text-dim]="!a.last_seen">{{ a.last_seen ? hace(a.last_seen) : 'nunca' }}</td>
            <td><button class="lnk del" (click)="eliminar(a)">Eliminar</button></td></tr>
        }
        @if (lista().length === 0) { <tr><td colspan="6" class="text-dim">Sin agentes.</td></tr> }
      </tbody>
    </table>
  `,
  styles: [`
    .head { display: flex; align-items: center; gap: 14px; margin: 8px 0 10px; }
    h1 { font-size: 18px; margin: 0; }
    .intro { font-size: 12.5px; margin: 0 0 12px; max-width: 820px; }
    .intro code { background: #eef3f0; padding: 1px 5px; border-radius: 4px; }
    .form { display: flex; gap: 8px; margin-bottom: 12px; }
    .form input { padding: 6px 8px; border: 1px solid var(--border); border-radius: 7px; font: inherit; }
    .token { background: #fffbe6; border: 1px solid #f0d27a; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; }
    .token code { font-family: ui-monospace, Consolas, monospace; word-break: break-all; }
    .tabla { width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; border: 1px solid var(--border); border-radius: var(--radius); }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
    .btn { background: var(--brand, #1b6b3a); color: #fff; border: 0; border-radius: 8px; padding: 7px 14px; cursor: pointer; font-weight: 600; }
    .lnk { border: 0; background: none; color: var(--brand, #1b6b3a); cursor: pointer; font-size: 12px; } .lnk.del { color: #c0392b; }
  `],
})
export class Agentes implements OnInit {
  private svc = inject(OperacionService);
  fecha = fecha; hace = hace;

  lista = signal<Agente[]>([]);
  form = signal(false);
  token = signal<string | null>(null);
  fNombre = ''; fRecurso?: number;

  ngOnInit(): void { this.cargar(); }
  cargar(): void { this.svc.agentes().subscribe({ next: (p) => this.lista.set(p.data) }); }
  crear(): void {
    this.svc.crearAgente({ nombre: this.fNombre, recurso_id: this.fRecurso || null }).subscribe({
      next: (r) => { this.token.set(r.token); this.form.set(false); this.fNombre = ''; this.fRecurso = undefined; this.cargar(); },
      error: (e) => alert('No se pudo crear el agente: ' + (e?.error?.message ?? 'error')),
    });
  }
  eliminar(a: Agente): void {
    if (!confirm(`¿Eliminar agente "${a.nombre}"?`)) return;
    this.svc.eliminarAgente(a.id).subscribe({
      next: () => this.cargar(),
      error: (e) => alert('No se pudo eliminar el agente: ' + (e?.error?.message ?? 'error')),
    });
  }
}
