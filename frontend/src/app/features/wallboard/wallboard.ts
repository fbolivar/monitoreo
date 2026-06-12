import { Component, ElementRef, OnDestroy, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription, interval } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Estado, Incidencia, Recurso, Severidad } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { TelemetriaService } from '../../core/telemetria.service';

const PESO: Record<Estado, number> = { down: 5, degraded: 4, unknown: 3, maintenance: 2, up: 1 };

const ETIQUETA: Record<Estado, string> = {
  up: 'Operativo', degraded: 'Degradado', down: 'Caído', unknown: 'Sin dato', maintenance: 'Mant.',
};

// Abreviatura por tipo de recurso (chip cuadrado en la fila de alerta).
const TIPO_ABREV: Record<string, string> = {
  firewall: 'FW', servidor: 'SRV', switch_lan: 'SW', switch_san: 'SAN',
  nas: 'NAS', ups: 'UPS', starlink: 'SAT', fibra_wan: 'WAN', sitio_web: 'WEB',
};

export interface Alerta {
  recurso: Recurso;
  estado: Estado;
  severidad: Severidad | null;
  titulo: string;
  desde: string | null;   // ISO: inicio de la incidencia o último chequeo
  reconocida: boolean;
}

export interface SedeSalud {
  sitio: string;
  total: number;
  up: number;
  problemas: number;
  peor: Estado;
  conteo: Record<Estado, number>;
}

@Component({
  selector: 'app-wallboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './wallboard.html',
  styleUrl: './wallboard.scss',
})
export class Wallboard implements OnInit, OnDestroy {
  private svc = inject(RecursosService);
  private tel = inject(TelemetriaService);

  recursos = signal<Recurso[]>([]);
  incidencias = signal<Incidencia[]>([]);
  enVivo = signal(false);
  reloj = signal(this.horaActual());

  /** Pausa el auto-scroll mientras el cursor está sobre la lista. */
  scrollHover = false;
  private listaRef = viewChild<ElementRef<HTMLElement>>('lista');

  private pollSub?: Subscription;
  private relojSub?: Subscription;
  private scrollSub?: Subscription;
  private scrollPausa = 45;

  resumen = computed(() => {
    const r: Record<Estado, number> = { up: 0, degraded: 0, down: 0, unknown: 0, maintenance: 0 };
    for (const x of this.recursos()) r[x.estado_actual] = (r[x.estado_actual] ?? 0) + 1;
    return r;
  });

  total = computed(() => this.recursos().length);

  /** % operativo sobre lo evaluable (excluye mantenimiento). */
  operatividad = computed(() => {
    const r = this.resumen();
    const evaluables = r.up + r.degraded + r.down + r.unknown;
    return evaluables ? Math.round((r.up / evaluables) * 1000) / 10 : 100;
  });

  nivelDispo = computed(() => {
    const d = this.operatividad();
    return d >= 99 ? 'ok' : d >= 95 ? 'warn' : 'bad';
  });

  /** Incidencia activa más severa por recurso. */
  private incidenciaPorRecurso = computed(() => {
    const m = new Map<number, Incidencia>();
    for (const i of this.incidencias()) {
      if (i.estado === 'resuelta') continue;
      const prev = m.get(i.recurso_id);
      if (!prev || this.sevPeso(i.severidad) > this.sevPeso(prev.severidad)) m.set(i.recurso_id, i);
    }
    return m;
  });

  /** Recursos con problema (down/degraded/unknown), activos, enriquecidos y ordenados. */
  alertas = computed<Alerta[]>(() => {
    const inc = this.incidenciaPorRecurso();
    const conProblema = this.recursos().filter(
      (r) => r.activo !== false && (r.estado_actual === 'down' || r.estado_actual === 'degraded' || r.estado_actual === 'unknown'),
    );
    return conProblema
      .map<Alerta>((r) => {
        const i = inc.get(r.id);
        return {
          recurso: r,
          estado: r.estado_actual,
          severidad: i?.severidad ?? null,
          titulo: i?.titulo ?? (r.hostname ?? r.tipo?.nombre ?? ''),
          desde: i?.abierta_at ?? r.ultimo_chequeo_at ?? null,
          reconocida: i?.estado === 'reconocida',
        };
      })
      .sort((a, b) => PESO[b.estado] - PESO[a.estado] || this.ms(a.desde) - this.ms(b.desde));
  });

  /** Top de incidencias por duración pura (independiente de severidad). */
  topDuracion = computed(() => {
    this.reloj(); // recalcula cada segundo para que la barra avance en vivo
    const ahora = Date.now();
    const items = this.alertas()
      .filter((a) => a.desde)
      .map((a) => ({ alerta: a, min: Math.max(1, Math.floor((ahora - new Date(a.desde!).getTime()) / 60_000)) }))
      .sort((x, y) => y.min - x.min)
      .slice(0, 6);
    const max = items.length ? items[0].min : 1;
    return items.map((i) => ({ ...i, pct: Math.max(6, Math.round((i.min / max) * 100)) }));
  });

  /** Salud compacta por sede, peor estado primero. */
  sedes = computed<SedeSalud[]>(() => {
    const porSitio = new Map<string, Recurso[]>();
    for (const x of this.recursos()) {
      const s = x.sitio?.nombre ?? 'Sin sitio';
      if (!porSitio.has(s)) porSitio.set(s, []);
      porSitio.get(s)!.push(x);
    }
    return [...porSitio.entries()]
      .map<SedeSalud>(([sitio, rs]) => {
        const conteo: Record<Estado, number> = { up: 0, degraded: 0, down: 0, unknown: 0, maintenance: 0 };
        for (const r of rs) conteo[r.estado_actual]++;
        const peor = rs.reduce<Estado>((p, x) => (PESO[x.estado_actual] > PESO[p] ? x.estado_actual : p), 'up');
        return { sitio, total: rs.length, up: conteo.up, problemas: conteo.down + conteo.degraded + conteo.unknown, peor, conteo };
      })
      .sort((a, b) => PESO[b.peor] - PESO[a.peor] || b.total - a.total || a.sitio.localeCompare(b.sitio));
  });

  ngOnInit(): void {
    this.refrescar();
    this.pollSub = interval(environment.refreshMs).subscribe(() => this.refrescar());
    this.relojSub = interval(1000).subscribe(() => this.reloj.set(this.horaActual()));
    this.scrollSub = interval(35).subscribe(() => this.autoScroll());
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
    this.relojSub?.unsubscribe();
    this.scrollSub?.unsubscribe();
  }

  /** Desplaza la lista de alertas lentamente; al llegar al final vuelve arriba y pausa. */
  private autoScroll(): void {
    if (this.scrollHover) return;
    const el = this.listaRef()?.nativeElement;
    if (!el) return;
    const max = el.scrollHeight - el.clientHeight;
    if (max <= 4) return; // todo cabe, no hace falta scroll
    if (this.scrollPausa > 0) { this.scrollPausa--; return; }
    if (el.scrollTop >= max - 1) { el.scrollTop = 0; this.scrollPausa = 70; }
    else { el.scrollTop += 1; }
  }

  abrev(r: Recurso): string {
    const c = r.tipo?.codigo ?? '';
    return TIPO_ABREV[c] ?? (c ? c.slice(0, 3).toUpperCase() : '—');
  }

  etiqueta(e: Estado): string {
    return ETIQUETA[e];
  }

  /** Texto "hace X" relativo al instante actual (se recalcula con el reloj). */
  hace(iso: string | null): string {
    if (!iso) return '';
    const ms = Date.now() - new Date(iso).getTime();
    if (ms < 60_000) return 'hace <1 min';
    const min = Math.floor(ms / 60_000);
    if (min < 60) return `hace ${min} min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `hace ${h} h ${min % 60} min`;
    const d = Math.floor(h / 24);
    return `hace ${d} d ${h % 24} h`;
  }

  private refrescar(): void {
    this.svc.listar().subscribe({
      next: (p) => { this.recursos.set(p.data); this.enVivo.set(true); },
      error: () => this.enVivo.set(false),
    });
    this.tel.incidencias({ per_page: 200 }).subscribe({
      next: (p) => this.incidencias.set(p.data),
      error: () => { /* sin enriquecimiento de duración si falla */ },
    });
  }

  private sevPeso(s: Severidad | null | undefined): number {
    return s === 'critical' ? 3 : s === 'warning' ? 2 : s === 'info' ? 1 : 0;
  }

  private ms(iso: string | null): number {
    return iso ? new Date(iso).getTime() : Date.now();
  }

  private horaActual(): string {
    return new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
}
