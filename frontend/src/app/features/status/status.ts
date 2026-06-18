import { DatePipe } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { StatusResp } from '../../core/models';

/** Página de estado PÚBLICA (#12): sin login, para usuarios finales. */
@Component({
  selector: 'app-status',
  standalone: true,
  imports: [DatePipe],
  template: `
    <div class="sp-wrap">
      <header class="sp-head">
        <h1>Estado de los servicios</h1>
        @if (data(); as d) {
          <div class="banner" [class.ok]="d.operativo" [class.bad]="!d.operativo">
            {{ d.operativo ? 'Todos los sistemas operativos' : 'Incidencias en curso' }}
          </div>
          <span class="upd">Actualizado: {{ d.actualizado | date:'short' }}</span>
        }
      </header>

      @if (data(); as d) {
        <div class="sedes">
          @for (s of d.sedes; track s.sitio) {
            <div class="sede" [attr.data-e]="s.estado">
              <div class="dot"></div>
              <div class="info">
                <b>{{ s.sitio }}</b>
                <span>{{ s.up }}/{{ s.total }} operativos
                  @if (s.down) { · {{ s.down }} caído(s) }
                  @if (s.degraded) { · {{ s.degraded }} degradado(s) }
                </span>
              </div>
            </div>
          }
        </div>
      } @else {
        <p class="cargando">Cargando estado…</p>
      }
      <footer class="sp-foot">SIMON · Parques Nacionales Naturales de Colombia</footer>
    </div>
  `,
  styles: [`
    .sp-wrap { max-width: 760px; margin: 0 auto; padding: 32px 18px; font-family: system-ui, sans-serif; }
    .sp-head { text-align: center; margin-bottom: 24px; }
    h1 { font-size: 22px; margin: 0 0 14px; color: #14532d; }
    .banner { display: inline-block; padding: 10px 22px; border-radius: 10px; font-weight: 700; color: #fff; }
    .banner.ok { background: #1b8a3a; }
    .banner.bad { background: #d11d1d; }
    .upd { display: block; margin-top: 8px; font-size: 12px; color: #6b7280; }
    .sedes { display: grid; gap: 10px; }
    .sede { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fff; }
    .sede .dot { width: 13px; height: 13px; border-radius: 50%; background: #9ca3af; flex: 0 0 auto; }
    .sede[data-e=up] .dot { background: #1b8a3a; }
    .sede[data-e=degraded] .dot { background: #e0a400; }
    .sede[data-e=down] .dot { background: #d11d1d; }
    .sede[data-e=maintenance] .dot { background: #3b82f6; }
    .info { display: flex; flex-direction: column; }
    .info b { font-size: 14px; }
    .info span { font-size: 12px; color: #6b7280; }
    .cargando { text-align: center; color: #6b7280; }
    .sp-foot { text-align: center; margin-top: 28px; font-size: 11px; color: #9ca3af; }
  `],
})
export class Status implements OnInit, OnDestroy {
  private api = inject(ApiService);
  data = signal<StatusResp | null>(null);
  private timer?: ReturnType<typeof setInterval>;

  ngOnInit(): void { this.cargar(); this.timer = setInterval(() => this.cargar(), 30000); }
  ngOnDestroy(): void { if (this.timer) clearInterval(this.timer); }

  cargar(): void {
    this.api.get<StatusResp>('/status').subscribe({ next: (d) => this.data.set(d), error: () => {} });
  }
}
