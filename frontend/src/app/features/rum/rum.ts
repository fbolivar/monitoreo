import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RumResp } from '../../core/models';
import { OperacionService } from '../../core/operacion.service';

/** APM / RUM (#13): experiencia real del usuario + trazas. */
@Component({
  selector: 'app-rum',
  standalone: true,
  imports: [DecimalPipe],
  template: `
    <div class="head">
      <h1>Experiencia de usuario <span class="text-dim">· RUM / APM</span></h1>
      <div class="rangos">
        @for (r of ['1h','24h','7d']; track r) {
          <button class="r" [class.activo]="rango() === r" (click)="cambiar(r)">{{ r }}</button>
        }
      </div>
    </div>
    <p class="intro text-dim">Tiempos REALES de carga medidos en el navegador de los usuarios (beacon
      <code>/api/ingest/rum</code>) y trazas de servicios (<code>/api/ingest/span</code>, estilo OpenTelemetry).</p>

    @if (data(); as d) {
      <div class="kpis">
        <div class="kpi"><b>{{ d.kpis.muestras }}</b><span>muestras</span></div>
        <div class="kpi"><b>{{ d.kpis.avg_ms | number:'1.0-0' }} ms</b><span>carga media</span></div>
        <div class="kpi"><b>{{ d.kpis.p95_ms | number:'1.0-0' }} ms</b><span>p95</span></div>
        <div class="kpi" [class.alerta]="d.errores > 0"><b>{{ d.errores }}</b><span>errores JS</span></div>
      </div>

      <section class="card">
        <h2>Páginas más lentas</h2>
        <table><thead><tr><th>URL</th><th class="n">Muestras</th><th class="n">Media</th><th class="n">Máx</th></tr></thead>
          <tbody>
            @for (u of d.por_url; track u.url) {
              <tr><td class="mono">{{ u.url }}</td><td class="n">{{ u.muestras }}</td>
                <td class="n">{{ u.avg_ms | number:'1.0-0' }} ms</td><td class="n">{{ u.max_ms | number:'1.0-0' }} ms</td></tr>
            }
            @if (d.por_url.length === 0) { <tr><td colspan="4" class="text-dim">Sin datos. Embebe el beacon (ver docs).</td></tr> }
          </tbody></table>
      </section>

      @if (d.spans.length) {
        <section class="card">
          <h2>Servicios (trazas)</h2>
          <table><thead><tr><th>Servicio</th><th class="n">Spans</th><th class="n">Duración media</th></tr></thead>
            <tbody>@for (s of d.spans; track s.servicio) {
              <tr><td>{{ s.servicio }}</td><td class="n">{{ s.n }}</td><td class="n">{{ s.avg_ms | number:'1.0-0' }} ms</td></tr>
            }</tbody></table>
        </section>
      }
    } @else { <p class="text-dim">Cargando…</p> }
  `,
  styles: [`
    .head { display: flex; align-items: center; gap: 16px; margin: 8px 0 6px; }
    h1 { font-size: 18px; margin: 0; }
    .intro { font-size: 12.5px; margin: 0 0 14px; max-width: 820px; }
    .intro code { background: #eef3f0; padding: 1px 5px; border-radius: 4px; }
    .rangos { display: inline-flex; gap: 4px; background: #eef3f0; padding: 4px; border-radius: 9px; }
    .rangos .r { border: 0; background: transparent; cursor: pointer; font-size: 12.5px; font-weight: 600; padding: 5px 12px; border-radius: 7px; }
    .rangos .r.activo { background: #fff; box-shadow: 0 1px 3px #0000001a; color: var(--brand, #1b6b3a); }
    .kpis { display: flex; gap: 24px; margin-bottom: 14px; }
    .kpi { display: flex; flex-direction: column; } .kpi b { font-size: 22px; } .kpi span { font-size: 11px; color: var(--text-dim); text-transform: uppercase; }
    .kpi.alerta b { color: #c0392b; }
    .card { background: #fff; border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; margin-bottom: 14px; }
    .card h2 { font-size: 14px; margin: 0 0 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
    th, td { text-align: left; padding: 6px 9px; border-bottom: 1px solid var(--border); }
    .n { text-align: right; font-variant-numeric: tabular-nums; }
    .mono { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; }
  `],
})
export class Rum implements OnInit {
  private svc = inject(OperacionService);
  data = signal<RumResp | null>(null);
  rango = signal<'1h' | '24h' | '7d'>('24h');

  ngOnInit(): void { this.cargar(); }
  cambiar(r: string): void { this.rango.set(r as any); this.cargar(); }
  cargar(): void { this.svc.rum(this.rango()).subscribe({ next: (d) => this.data.set(d), error: () => {} }); }
}
