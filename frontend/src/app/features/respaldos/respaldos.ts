import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Backup } from '../../core/models';
import { OperacionService } from '../../core/operacion.service';
import { fecha } from '../../shared/tiempo';

/** Respaldos del sistema (.pnnc, formato propio PNNC): generar y EXPORTAR backups
 * de la BD para llevarlos fuera del servidor. Solo admin. */
@Component({
  selector: 'app-respaldos',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="head">
      <h1>Respaldos del sistema</h1>
      <button class="btn" (click)="form.set(!form())" [disabled]="generando()">+ Generar respaldo</button>
    </div>
    <p class="intro text-dim">Genera una copia completa de la base de datos en formato propio
      <code>.pnnc</code> (Parques Nacionales) y <b>expórtala</b> para guardarla fuera del servidor.
      Cada archivo lleva su integridad (sha256) y metadatos. La restauración se hace en el servidor
      con <code>infra/deploy/restaurar_pnnc.sh</code>.</p>

    @if (form()) {
      <div class="form">
        <input [(ngModel)]="fNota" placeholder="Nota (opcional, ej. antes de migración)" maxlength="200">
        <input [(ngModel)]="fPass" type="password" placeholder="Passphrase (opcional, cifra el .pnnc)" autocomplete="new-password">
        <button class="btn" (click)="generar()" [disabled]="generando()">{{ generando() ? 'Generando…' : 'Generar' }}</button>
        <button class="lnk" (click)="form.set(false)" [disabled]="generando()">Cancelar</button>
      </div>
      @if (generando()) { <p class="text-dim aviso">⏳ Volcando la base de datos… puede tardar ~30 s, no cierres la página.</p> }
    }
    @if (msg(); as m) { <p class="ok-msg">{{ m }}</p> }

    <table class="tabla">
      <thead><tr><th>Archivo</th><th>Creado</th><th>Tamaño</th><th>Cifrado</th><th>Nota</th><th>Integridad</th><th></th></tr></thead>
      <tbody>
        @for (b of lista(); track b.id) {
          <tr>
            <td><b>{{ b.id }}</b></td>
            <td class="text-dim">{{ b.creado_en ? fecha(b.creado_en) : '—' }}</td>
            <td>{{ humano(b.tam) }}</td>
            <td>@if (b.cifrado && b.cifrado !== 'none') { <span class="tag enc">🔒 sí</span> } @else { <span class="text-dim">no</span> }</td>
            <td class="text-dim">{{ b.nota || '—' }}</td>
            <td class="mono text-dim" [title]="b.sha256 || ''">{{ b.sha256 ? b.sha256.slice(0, 12) + '…' : '—' }}</td>
            <td class="acc">
              <button class="lnk" (click)="descargar(b)">Descargar</button>
              <button class="lnk del" (click)="eliminar(b)">Eliminar</button>
            </td>
          </tr>
        }
        @if (lista().length === 0) { <tr><td colspan="7" class="text-dim">Sin respaldos. Genera el primero.</td></tr> }
      </tbody>
    </table>
  `,
  styles: [`
    .head { display: flex; align-items: center; gap: 14px; margin: 8px 0 10px; }
    h1 { font-size: 18px; margin: 0; }
    .intro { font-size: 12.5px; margin: 0 0 12px; max-width: 880px; }
    .intro code { background: #eef3f0; padding: 1px 5px; border-radius: 4px; }
    .form { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
    .form input { padding: 6px 8px; border: 1px solid var(--border); border-radius: 7px; font: inherit; min-width: 280px; }
    .aviso { font-size: 12.5px; margin: 0 0 12px; }
    .ok-msg { background: #e9f7ef; border: 1px solid #9cd6b0; border-radius: 8px; padding: 8px 12px; font-size: 13px; margin: 0 0 12px; }
    .tabla { width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; border: 1px solid var(--border); border-radius: var(--radius); }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
    .mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
    .tag.enc { color: #1b6b3a; font-weight: 600; }
    .acc { white-space: nowrap; }
    .btn { background: var(--brand, #1b6b3a); color: #fff; border: 0; border-radius: 8px; padding: 7px 14px; cursor: pointer; font-weight: 600; }
    .btn:disabled { opacity: .6; cursor: default; }
    .lnk { border: 0; background: none; color: var(--brand, #1b6b3a); cursor: pointer; font-size: 12px; padding: 0 4px; } .lnk.del { color: #c0392b; }
  `],
})
export class Respaldos implements OnInit {
  private svc = inject(OperacionService);
  fecha = fecha;

  lista = signal<Backup[]>([]);
  form = signal(false);
  generando = signal(false);
  msg = signal<string | null>(null);
  fNota = ''; fPass = '';

  ngOnInit(): void { this.cargar(); }

  cargar(): void { this.svc.backups().subscribe({ next: (r) => this.lista.set(r.data), error: () => {} }); }

  generar(): void {
    this.generando.set(true);
    this.msg.set(null);
    this.svc.generarBackup({ nota: this.fNota || undefined, passphrase: this.fPass || undefined }).subscribe({
      next: (r) => {
        this.generando.set(false); this.form.set(false);
        this.fNota = ''; this.fPass = '';
        this.msg.set('Respaldo generado: ' + r.data.id);
        this.cargar();
      },
      error: (e) => {
        this.generando.set(false);
        alert('No se pudo generar el respaldo: ' + (e?.error?.message ?? 'error'));
      },
    });
  }

  descargar(b: Backup): void {
    this.svc.descargarBackup(b.id).subscribe({
      next: (resp) => {
        const blob = resp.body;
        if (!blob) { return; }
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = b.id;
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      },
      error: (e) => alert('No se pudo descargar: ' + (e?.error?.message ?? 'error')),
    });
  }

  eliminar(b: Backup): void {
    if (!confirm(`¿Eliminar el respaldo "${b.id}"? Esta acción no se puede deshacer.`)) { return; }
    this.svc.eliminarBackup(b.id).subscribe({
      next: () => this.cargar(),
      error: (e) => alert('No se pudo eliminar: ' + (e?.error?.message ?? 'error')),
    });
  }

  humano(bytes: number): string {
    if (!bytes) { return '0 B'; }
    const u = ['B', 'KB', 'MB', 'GB']; let i = 0; let n = bytes;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
  }
}
