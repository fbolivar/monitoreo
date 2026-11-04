import { Component, OnInit, inject, input, signal } from '@angular/core';
import { TelemetriaService } from '../../core/telemetria.service';
import { LineChart, Punto } from '../../shared/line-chart';

/** Widget: serie temporal de una métrica de un recurso. Se autogestiona. */
@Component({
  selector: 'app-widget-metrica',
  standalone: true,
  imports: [LineChart],
  template: `
    @if (cargando()) { <p class="text-dim">Cargando…</p> }
    @else if (serie().length === 0) { <p class="text-dim">Sin datos para {{ metrica() }} ({{ rango() }}).</p> }
    @else { <app-line-chart [data]="serie()" [label]="metrica()" [unidad]="unidad()" /> }
  `,
})
export class WidgetMetrica implements OnInit {
  private tele = inject(TelemetriaService);
  recursoId = input.required<number>();
  metrica = input.required<string>();
  rango = input<'1h' | '24h' | '7d'>('24h');

  serie = signal<Punto[]>([]);
  unidad = signal('');
  cargando = signal(true);

  ngOnInit(): void {
    const ms = { '1h': 3600, '24h': 86400, '7d': 604800 }[this.rango()];
    const desde = new Date(Date.now() - ms * 1000).toISOString();
    this.tele.metricas({ recurso_id: this.recursoId(), metrica: this.metrica(), desde, per_page: 1000 })
      .subscribe({
        next: (p) => {
          const ms2 = p.data.filter((m) => m.metrica === this.metrica());
          this.serie.set(ms2.map((m) => ({ ts: m.ts, valor: m.valor })));
          if (ms2[0]?.unidad) this.unidad.set(ms2[0].unidad);
          this.cargando.set(false);
        },
        error: () => this.cargando.set(false),
      });
  }
}
