import { Component, computed, input } from '@angular/core';

export interface Punto { ts: string; valor: number; }

/** Gráfica de línea SVG sin dependencias, responsive por viewBox. */
@Component({
  selector: 'app-line-chart',
  standalone: true,
  template: `
    <div class="lc card">
      <div class="lc-h">
        <span>{{ label() }}</span>
        <span class="text-dim">
          @if (ultimo() !== null) { {{ ultimo() }}{{ unidad() }} · } min {{ min() }} · máx {{ max() }}
        </span>
      </div>
      @if (puntos().length < 2) {
        <div class="vacio text-dim">Sin datos suficientes</div>
      } @else {
        <svg viewBox="0 0 600 140" preserveAspectRatio="none" class="svg">
          <polyline [attr.points]="area()" class="area" />
          <polyline [attr.points]="linea()" class="linea" />
        </svg>
      }
    </div>
  `,
  styles: [
    `
      .lc { padding: 10px 12px; }
      .lc-h { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px; }
      .svg { width: 100%; height: 90px; display: block; }
      .linea { fill: none; stroke: var(--accent); stroke-width: 2; vector-effect: non-scaling-stroke; }
      .area { fill: color-mix(in srgb, var(--accent) 18%, transparent); stroke: none; }
      .vacio { height: 90px; display: grid; place-items: center; font-size: 12px; }
    `,
  ],
})
export class LineChart {
  data = input.required<Punto[]>();
  label = input('');
  unidad = input('');

  puntos = computed(() =>
    [...this.data()].sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()),
  );

  private valores = computed(() => this.puntos().map((p) => p.valor));
  min = computed(() => (this.valores().length ? Math.min(...this.valores()) : 0));
  max = computed(() => (this.valores().length ? Math.max(...this.valores()) : 0));
  ultimo = computed(() => {
    const v = this.valores();
    return v.length ? v[v.length - 1] : null;
  });

  private coords = computed(() => {
    const pts = this.puntos();
    const n = pts.length;
    if (n < 2) return [] as [number, number][];
    const lo = this.min();
    const hi = this.max();
    const span = hi - lo || 1;
    return pts.map((p, i): [number, number] => {
      const x = (i / (n - 1)) * 600;
      const y = 130 - ((p.valor - lo) / span) * 120 - 5;
      return [x, y];
    });
  });

  linea = computed(() => this.coords().map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' '));
  area = computed(() => {
    const c = this.coords();
    if (!c.length) return '';
    return `0,140 ${this.linea()} 600,140`;
  });
}
