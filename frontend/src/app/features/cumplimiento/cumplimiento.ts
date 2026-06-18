import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';
import { PoliticaCumplimiento, ResultadoCumplimiento } from '../../core/models';
import { OperacionService } from '../../core/operacion.service';
import { fecha } from '../../shared/tiempo';

/** Cumplimiento de configuración (#7): políticas (golden config) + resultados. */
@Component({
  selector: 'app-cumplimiento',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="head"><h1>Cumplimiento de configuración</h1></div>
    <p class="intro text-dim">Valida la última config respaldada de cada equipo contra políticas
      (debe / no debe contener, o regex). El worker evalúa periódicamente y avisa al incumplir.</p>

    <section class="card">
      <h2>Incumplimientos actuales</h2>
      @if (incumplen().length === 0) { <p class="text-dim">Sin incumplimientos. 🎉</p> }
      @else {
        <table class="tabla">
          <thead><tr><th>Recurso</th><th>Política</th><th>Severidad</th><th>Detalle</th><th>Visto</th></tr></thead>
          <tbody>
            @for (r of incumplen(); track r.id) {
              <tr><td><b>{{ r.recurso_nombre }}</b></td><td>{{ r.politica }}</td>
                <td><span class="sev" [attr.data-s]="r.severidad">{{ r.severidad }}</span></td>
                <td class="text-dim">{{ r.detalle }}</td><td class="text-dim">{{ fecha(r.ts) }}</td></tr>
            }
          </tbody>
        </table>
      }
    </section>

    <section class="card">
      <div class="ch"><h2>Políticas</h2>
        @if (auth.puedeEditar()) { <button class="btn" (click)="agregar()">+ Política</button> }
      </div>
      @if (form()) {
        <div class="form">
          <input [(ngModel)]="fNombre" placeholder="Nombre">
          <select [(ngModel)]="fTipo">
            <option value="contiene">debe contener</option>
            <option value="no_contiene">no debe contener</option>
            <option value="regex">regex</option>
          </select>
          <input [(ngModel)]="fPatron" placeholder="Patrón / texto">
          <select [(ngModel)]="fSev"><option value="info">info</option><option value="warning">warning</option><option value="critical">critical</option></select>
          <button class="btn" (click)="guardar()">Guardar</button>
          <button class="lnk" (click)="form.set(false)">Cancelar</button>
        </div>
      }
      <table class="tabla">
        <thead><tr><th>Nombre</th><th>Regla</th><th>Sev.</th><th>Activa</th><th></th></tr></thead>
        <tbody>
          @for (p of politicas(); track p.id) {
            <tr><td><b>{{ p.nombre }}</b></td>
              <td class="text-dim">{{ p.tipo }} «{{ p.patron }}»</td>
              <td>{{ p.severidad }}</td><td>{{ p.activo ? 'Sí' : 'No' }}</td>
              <td>@if (auth.puedeEditar()) { <button class="lnk del" (click)="eliminar(p)">Eliminar</button> }</td></tr>
          }
          @if (politicas().length === 0) { <tr><td colspan="5" class="text-dim">Sin políticas.</td></tr> }
        </tbody>
      </table>
    </section>
  `,
  styles: [`
    .head h1 { font-size: 18px; margin: 8px 0; }
    .intro { font-size: 12.5px; margin: 0 0 14px; max-width: 780px; }
    .card { background: #fff; border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; margin-bottom: 14px; }
    .card h2 { font-size: 14px; margin: 0 0 10px; }
    .ch { display: flex; align-items: center; justify-content: space-between; }
    .tabla { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 7px 9px; border-bottom: 1px solid var(--border); }
    .sev[data-s=critical] { color: #c0392b; font-weight: 700; }
    .sev[data-s=warning] { color: #9a6b00; font-weight: 600; }
    .form { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .form input, .form select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 7px; font: inherit; }
    .btn { background: var(--brand, #1b6b3a); color: #fff; border: 0; border-radius: 8px; padding: 6px 13px; cursor: pointer; font-weight: 600; }
    .lnk { border: 0; background: none; color: var(--brand, #1b6b3a); cursor: pointer; font-size: 12px; }
    .lnk.del { color: #c0392b; }
  `],
})
export class Cumplimiento implements OnInit {
  private svc = inject(OperacionService);
  auth = inject(AuthService);
  fecha = fecha;

  politicas = signal<PoliticaCumplimiento[]>([]);
  resultados = signal<ResultadoCumplimiento[]>([]);
  form = signal(false);
  fNombre = ''; fTipo: 'contiene' | 'no_contiene' | 'regex' = 'contiene'; fPatron = ''; fSev = 'warning';

  incumplen = () => this.resultados().filter((r) => !r.cumple);

  ngOnInit(): void { this.cargar(); }
  cargar(): void {
    this.svc.politicas().subscribe({ next: (p) => this.politicas.set(p.data) });
    this.svc.resultadosCumplimiento().subscribe({ next: (p) => this.resultados.set(p.data) });
  }
  agregar(): void { this.fNombre = ''; this.fPatron = ''; this.form.set(true); }
  guardar(): void {
    this.svc.crearPolitica({ nombre: this.fNombre, tipo: this.fTipo, patron: this.fPatron, severidad: this.fSev as any, activo: true })
      .subscribe({ next: () => { this.form.set(false); this.cargar(); } });
  }
  eliminar(p: PoliticaCumplimiento): void {
    if (!confirm(`¿Eliminar política "${p.nombre}"?`)) return;
    this.svc.eliminarPolitica(p.id).subscribe({ next: () => this.cargar() });
  }
}
