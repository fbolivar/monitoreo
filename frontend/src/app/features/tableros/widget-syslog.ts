import { Component, OnInit, inject, input, signal } from '@angular/core';
import { Severidad, SyslogEvento } from '../../core/models';
import { SyslogService } from '../../core/syslog.service';
import { fecha } from '../../shared/tiempo';

/** Widget: últimos eventos syslog (opcionalmente filtrados por severidad). */
@Component({
  selector: 'app-widget-syslog',
  standalone: true,
  template: `
    @if (cargando()) { <p class="text-dim">Cargando…</p> }
    @else if (eventos().length === 0) { <p class="text-dim">Sin eventos syslog.</p> }
    @else {
      <ul class="wsys">
        @for (e of eventos(); track e.id) {
          <li>
            <span class="d" [style.background]="color(e.severidad)"></span>
            <span class="t">{{ fecha(e.ts) }}</span>
            <span class="h">{{ e.hostname || e.source_ip }}</span>
            <span class="m">{{ e.mensaje }}</span>
          </li>
        }
      </ul>
    }
  `,
  styles: [`
    .wsys { list-style: none; margin: 0; padding: 0; font-size: 12px; }
    .wsys li { display: flex; gap: 6px; align-items: baseline; padding: 2px 0; border-bottom: 1px solid var(--border, #eee); }
    .wsys .d { width: 9px; height: 9px; border-radius: 50%; flex: 0 0 auto; align-self: center; }
    .wsys .t { color: var(--text-dim); white-space: nowrap; font-variant-numeric: tabular-nums; }
    .wsys .h { font-weight: 600; white-space: nowrap; }
    .wsys .m { font-family: ui-monospace, Consolas, monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  `],
})
export class WidgetSyslog implements OnInit {
  private svc = inject(SyslogService);
  fecha = fecha;
  limite = input<number>(10);
  severidad = input<Severidad | ''>('');

  eventos = signal<SyslogEvento[]>([]);
  cargando = signal(true);

  ngOnInit(): void {
    this.svc.listar({ per_page: this.limite(), severidad: this.severidad() || undefined }).subscribe({
      next: (p) => { this.eventos.set(p.data.slice(0, this.limite())); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }
  color(s: Severidad): string {
    return { critical: '#d11d1d', warning: '#e0a400', info: '#9aa0a6' }[s];
  }
}
