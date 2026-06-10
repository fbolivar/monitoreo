import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subscription, interval } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth.service';
import { Estado, ESTADO_LABEL, ESTADOS, Recurso } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';

interface GrupoTipo { tipo: string; recursos: Recurso[]; }
interface GrupoSitio { sitio: string; total: number; tipos: GrupoTipo[]; }

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit, OnDestroy {
  private recursosSvc = inject(RecursosService);
  auth = inject(AuthService);

  readonly estados = ESTADOS;
  readonly estadoLabel = ESTADO_LABEL;

  recursos = signal<Recurso[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);
  enVivo = signal(false);

  filtroEstado = signal<Estado | ''>('');
  busqueda = signal('');

  /** Etiqueta del filtro de estado activo (vacía si no hay). */
  labelFiltro = computed(() => {
    const e = this.filtroEstado();
    return e ? ESTADO_LABEL[e] : '';
  });

  private pollSub?: Subscription;
  readonly intervaloSeg = Math.round(environment.refreshMs / 1000);

  /** Conteo por estado (sobre todos los recursos, sin filtrar). */
  resumen = computed(() => {
    const r: Record<Estado, number> = { up: 0, degraded: 0, down: 0, unknown: 0, maintenance: 0 };
    for (const x of this.recursos()) r[x.estado_actual] = (r[x.estado_actual] ?? 0) + 1;
    return r;
  });

  filtrados = computed(() => {
    const est = this.filtroEstado();
    const q = this.busqueda().trim().toLowerCase();
    return this.recursos().filter((x) => {
      if (est && x.estado_actual !== est) return false;
      if (q && !(`${x.nombre} ${x.hostname ?? ''}`.toLowerCase().includes(q))) return false;
      return true;
    });
  });

  /** Agrupa por sitio y, dentro, por tipo. */
  grupos = computed<GrupoSitio[]>(() => {
    const porSitio = new Map<string, Recurso[]>();
    for (const x of this.filtrados()) {
      const s = x.sitio?.nombre ?? 'Sin sitio';
      (porSitio.get(s) ?? porSitio.set(s, []).get(s)!).push(x);
    }
    const orden: Record<Estado, number> = { down: 0, degraded: 1, unknown: 2, maintenance: 3, up: 4 };
    const result: GrupoSitio[] = [];
    for (const [sitio, lista] of porSitio) {
      const porTipo = new Map<string, Recurso[]>();
      for (const x of lista) {
        const t = x.tipo?.nombre ?? 'Otro';
        (porTipo.get(t) ?? porTipo.set(t, []).get(t)!).push(x);
      }
      const tipos: GrupoTipo[] = [...porTipo.entries()]
        .map(([tipo, recursos]) => ({
          tipo,
          recursos: recursos.sort((a, b) => orden[a.estado_actual] - orden[b.estado_actual]),
        }))
        .sort((a, b) => a.tipo.localeCompare(b.tipo));
      result.push({ sitio, total: lista.length, tipos });
    }
    return result.sort((a, b) => a.sitio.localeCompare(b.sitio));
  });

  ngOnInit(): void {
    this.cargar();
    // Opción B: refresco por POLLING (la BD es local; no hay Supabase Realtime).
    this.pollSub = interval(environment.refreshMs).subscribe(() => this.refrescar());
    this.enVivo.set(true);
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.recursosSvc.listar().subscribe({
      next: (page) => {
        this.recursos.set(page.data);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No se pudieron cargar los recursos. ¿API y sesión activas?');
        this.cargando.set(false);
      },
    });
  }

  /** Refresco silencioso (sin spinner) ejecutado por el polling. */
  private refrescar(): void {
    this.recursosSvc.listar().subscribe({
      next: (page) => {
        this.recursos.set(page.data);
        this.enVivo.set(true);
      },
      error: () => this.enVivo.set(false),
    });
  }

  hace(ts?: string | null): string {
    if (!ts) return '—';
    const seg = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
    if (seg < 60) return `${seg}s`;
    if (seg < 3600) return `${Math.floor(seg / 60)}m`;
    if (seg < 86400) return `${Math.floor(seg / 3600)}h`;
    return `${Math.floor(seg / 86400)}d`;
  }
}
