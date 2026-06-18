import { DecimalPipe } from '@angular/common';
import { Component, ElementRef, OnDestroy, OnInit, WritableSignal, computed, inject, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription, interval } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Estado, FlujoOverview, Incidencia, Recurso, Severidad, Sitio } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { TelemetriaService } from '../../core/telemetria.service';
import { COLOMBIA_DEPARTAMENTOS } from '../mapa/colombia-geo';

const PESO: Record<Estado, number> = { down: 5, degraded: 4, unknown: 3, maintenance: 2, up: 1 };
const ETIQUETA: Record<Estado, string> = {
  up: 'Operativo', degraded: 'Degradado', down: 'Caído', unknown: 'Sin dato', maintenance: 'Mant.',
};
const TIPO_ABREV: Record<string, string> = {
  firewall: 'FW', servidor: 'SRV', switch_lan: 'SW', switch_san: 'SAN',
  nas: 'NAS', ups: 'UPS', starlink: 'SAT', fibra_wan: 'WAN', sitio_web: 'WEB',
};

export interface Alerta {
  recurso: Recurso; estado: Estado; severidad: Severidad | null;
  titulo: string; desde: string | null; reconocida: boolean;
}
interface Marcador { nombre: string; x: number; y: number; estado: Estado; total: number; problemas: number; r: number; }

@Component({
  selector: 'app-wallboard',
  standalone: true,
  imports: [RouterLink, DecimalPipe],
  templateUrl: './wallboard.html',
  styleUrl: './wallboard.scss',
})
export class Wallboard implements OnInit, OnDestroy {
  private svc = inject(RecursosService);
  private tel = inject(TelemetriaService);

  recursos = signal<Recurso[]>([]);
  incidencias = signal<Incidencia[]>([]);
  sitios = signal<Sitio[]>([]);
  flujo = signal<FlujoOverview | null>(null);
  enVivo = signal(false);
  reloj = signal(this.horaActual());
  fecha = signal(this.fechaActual());
  pulso = signal(0);   // incrementa en cada refresh -> dispara animaciones

  // Mapa de Colombia (departamentos ya proyectados a 437×600).
  departamentos = COLOMBIA_DEPARTAMENTOS;
  readonly MW = 437; readonly MH = 600;

  scrollHover = false;
  private listaRef = viewChild<ElementRef<HTMLElement>>('lista');
  private pollSub?: Subscription; private relojSub?: Subscription; private scrollSub?: Subscription;
  private scrollPausa = 50;

  // Count-up animado de los números clave.
  dispAnim = signal(0); upAnim = signal(0); downAnim = signal(0);
  incAnim = signal(0); mbpsAnim = signal(0);

  resumen = computed(() => {
    const r: Record<Estado, number> = { up: 0, degraded: 0, down: 0, unknown: 0, maintenance: 0 };
    for (const x of this.recursos()) r[x.estado_actual] = (r[x.estado_actual] ?? 0) + 1;
    return r;
  });
  total = computed(() => this.recursos().length);
  operatividad = computed(() => {
    const r = this.resumen();
    const ev = r.up + r.degraded + r.down + r.unknown;
    return ev ? Math.round((r.up / ev) * 1000) / 10 : 100;
  });
  nivelDispo = computed(() => { const d = this.operatividad(); return d >= 99 ? 'ok' : d >= 95 ? 'warn' : 'bad'; });

  // Anillo SVG (circunferencia para el dash).
  readonly RING_R = 130;
  readonly RING_C = 2 * Math.PI * 130;
  ringOffset = computed(() => this.RING_C * (1 - this.dispAnim() / 100));

  incActivas = computed(() => this.incidencias().filter((i) => i.estado !== 'resuelta').length);
  incCriticas = computed(() => this.incidencias().filter((i) => i.estado !== 'resuelta' && i.severidad === 'critical').length);
  sedesConProblema = computed(() => this.marcadores().filter((m) => m.problemas > 0).length);

  private incidenciaPorRecurso = computed(() => {
    const m = new Map<number, Incidencia>();
    for (const i of this.incidencias()) {
      if (i.estado === 'resuelta') continue;
      const prev = m.get(i.recurso_id);
      if (!prev || this.sevPeso(i.severidad) > this.sevPeso(prev.severidad)) m.set(i.recurso_id, i);
    }
    return m;
  });

  alertas = computed<Alerta[]>(() => {
    const inc = this.incidenciaPorRecurso();
    return this.recursos()
      .filter((r) => r.activo !== false && (r.estado_actual === 'down' || r.estado_actual === 'degraded' || r.estado_actual === 'unknown'))
      .map<Alerta>((r) => {
        const i = inc.get(r.id);
        return {
          recurso: r, estado: r.estado_actual, severidad: i?.severidad ?? null,
          titulo: i?.titulo ?? (r.hostname ?? r.tipo?.nombre ?? ''),
          desde: i?.abierta_at ?? r.ultimo_chequeo_at ?? null,
          reconocida: i?.estado === 'reconocida',
        };
      })
      .sort((a, b) => PESO[b.estado] - PESO[a.estado] || this.ms(a.desde) - this.ms(b.desde));
  });

  topDuracion = computed(() => {
    this.reloj();
    const ahora = Date.now();
    const items = this.alertas().filter((a) => a.desde)
      .map((a) => ({ alerta: a, min: Math.max(1, Math.floor((ahora - new Date(a.desde!).getTime()) / 60_000)) }))
      .sort((x, y) => y.min - x.min).slice(0, 5);
    const max = items.length ? items[0].min : 1;
    return items.map((i) => ({ ...i, pct: Math.max(8, Math.round((i.min / max) * 100)) }));
  });

  // Marcadores del mapa: una sede por sitio con coordenadas, peor estado.
  marcadores = computed<Marcador[]>(() => {
    const porSitio = new Map<number, Recurso[]>();
    for (const r of this.recursos()) {
      if (r.sitio_id == null) continue;
      (porSitio.get(r.sitio_id) ?? porSitio.set(r.sitio_id, []).get(r.sitio_id)!).push(r);
    }
    return this.sitios()
      .filter((s) => s.latitud != null && s.longitud != null)
      .map<Marcador>((s) => {
        const rs = porSitio.get(s.id) ?? [];
        const peor = rs.reduce<Estado>((p, x) => (PESO[x.estado_actual] > PESO[p] ? x.estado_actual : p), 'up');
        const problemas = rs.filter((r) => ['down', 'degraded', 'unknown'].includes(r.estado_actual)).length;
        const p = this.proj(Number(s.longitud), Number(s.latitud));
        // Operativas: punto pequeño y limpio. Con problema: más grande (resalta).
        return { nombre: s.nombre, x: p.x, y: p.y, estado: rs.length ? peor : 'unknown', total: rs.length, problemas, r: problemas > 0 ? 9 : 4.5 };
      })
      .sort((a, b) => PESO[a.estado] - PESO[b.estado]);   // problemáticos al final = se dibujan encima
  });

  // NetFlow en vivo.
  trafSpark = computed<string>(() => {
    const v = this.flujo()?.spark.traffic ?? []; if (v.length < 2) return '';
    const w = 300, h = 60, max = Math.max(1, ...v), n = v.length;
    return v.map((x, i) => `${((i / (n - 1)) * w).toFixed(1)},${(h - (x / max) * (h - 6) - 3).toFixed(1)}`).join(' ');
  });
  trafArea = computed<string>(() => { const p = this.trafSpark(); return p ? `0,60 ${p} 300,60 Z` : ''; });
  topApp = computed(() => this.flujo()?.apps?.[0]?.app ?? '—');
  topTalker = computed(() => this.flujo()?.talkers?.[0]?.ip ?? '—');
  // Top hablante con detalle: IP que más tráfico genera + volumen y %.
  topTalkerInfo = computed(() => this.flujo()?.talkers?.[0] ?? null);

  ngOnInit(): void {
    this.refrescar();
    this.pollSub = interval(environment.refreshMs).subscribe(() => this.refrescar());
    this.relojSub = interval(1000).subscribe(() => { this.reloj.set(this.horaActual()); this.fecha.set(this.fechaActual()); });
    this.scrollSub = interval(35).subscribe(() => this.autoScroll());
  }
  ngOnDestroy(): void { this.pollSub?.unsubscribe(); this.relojSub?.unsubscribe(); this.scrollSub?.unsubscribe(); }

  private autoScroll(): void {
    if (this.scrollHover) return;
    const el = this.listaRef()?.nativeElement; if (!el) return;
    const max = el.scrollHeight - el.clientHeight; if (max <= 4) return;
    if (this.scrollPausa > 0) { this.scrollPausa--; return; }
    if (el.scrollTop >= max - 1) { el.scrollTop = 0; this.scrollPausa = 80; } else { el.scrollTop += 1; }
  }

  abrev(r: Recurso): string { const c = r.tipo?.codigo ?? ''; return TIPO_ABREV[c] ?? (c ? c.slice(0, 3).toUpperCase() : '—'); }
  recortar(s: string, n = 26): string { return s && s.length > n ? s.slice(0, n - 1) + '…' : s; }
  etiqueta(e: Estado): string { return ETIQUETA[e]; }
  hace(iso: string | null): string {
    if (!iso) return ''; const ms = Date.now() - new Date(iso).getTime();
    if (ms < 60_000) return 'hace <1 min'; const min = Math.floor(ms / 60_000);
    if (min < 60) return `hace ${min} min`; const h = Math.floor(min / 60);
    if (h < 24) return `hace ${h}h ${min % 60}m`; const d = Math.floor(h / 24); return `hace ${d}d ${h % 24}h`;
  }
  fmtBytes(b: number): string {
    if (!b) return '0 B'; const u = ['B', 'KB', 'MB', 'GB', 'TB']; let v = b, i = 0;
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; } return `${v.toFixed(v >= 100 || !i ? 0 : 1)} ${u[i]}`;
  }

  private refrescar(): void {
    this.svc.listar().subscribe({
      next: (p) => { this.recursos.set(p.data); this.enVivo.set(true); this.animar(); },
      error: () => this.enVivo.set(false),
    });
    this.tel.incidencias({ per_page: 200 }).subscribe({ next: (p) => this.incidencias.set(p.data), error: () => {} });
    this.svc.sitios().subscribe({ next: (p) => this.sitios.set(p.data), error: () => {} });
    this.svc.flujosOverview('1h').subscribe({ next: (f) => this.flujo.set(f), error: () => {} });
  }

  /** Tween de los números clave (count-up) + pulso para animaciones. */
  private animar(): void {
    this.pulso.update((v) => v + 1);
    this.tween(this.dispAnim, this.operatividad(), 900, 1);
    this.tween(this.upAnim, this.resumen().up, 700);
    this.tween(this.downAnim, this.resumen().down, 700);
    this.tween(this.incAnim, this.incActivas(), 700);
    this.tween(this.mbpsAnim, this.flujo()?.kpis.avg_mbps ?? 0, 900, 1);
  }
  private tween(sig: WritableSignal<number>, to: number, dur: number, dec = 0): void {
    const from = sig(); const ini = performance.now(); const f = 10 ** dec;
    const paso = (t: number) => {
      const k = Math.min(1, (t - ini) / dur); const e = 1 - Math.pow(1 - k, 3);
      sig.set(Math.round((from + (to - from) * e) * f) / f);
      if (k < 1) requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  }

  private proj(lon: number, lat: number): { x: number; y: number } {
    const LON_MIN = -79.1, LON_MAX = -66.8, LAT_MIN = -4.3, LAT_MAX = 12.6;
    return { x: ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * this.MW, y: ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * this.MH };
  }
  private sevPeso(s: Severidad | null | undefined): number { return s === 'critical' ? 3 : s === 'warning' ? 2 : s === 'info' ? 1 : 0; }
  private ms(iso: string | null): number { return iso ? new Date(iso).getTime() : Date.now(); }
  private horaActual(): string { return new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  private fechaActual(): string { return new Date().toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' }); }
}
