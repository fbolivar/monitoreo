import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription, interval } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Estado, Recurso } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';

interface SedeTile { sitio: string; total: number; peor: Estado; recursos: Recurso[]; }

const PESO: Record<Estado, number> = { down: 5, degraded: 4, unknown: 3, maintenance: 2, up: 1 };

@Component({
  selector: 'app-wallboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './wallboard.html',
  styleUrl: './wallboard.scss',
})
export class Wallboard implements OnInit, OnDestroy {
  private svc = inject(RecursosService);

  recursos = signal<Recurso[]>([]);
  enVivo = signal(false);
  reloj = signal(this.horaActual());

  private pollSub?: Subscription;
  private relojSub?: Subscription;

  resumen = computed(() => {
    const r: Record<Estado, number> = { up: 0, degraded: 0, down: 0, unknown: 0, maintenance: 0 };
    for (const x of this.recursos()) r[x.estado_actual] = (r[x.estado_actual] ?? 0) + 1;
    return r;
  });

  sedes = computed<SedeTile[]>(() => {
    const porSitio = new Map<string, Recurso[]>();
    for (const x of this.recursos()) {
      const s = x.sitio?.nombre ?? 'Sin sitio';
      (porSitio.get(s) ?? porSitio.set(s, []).get(s)!).push(x);
    }
    const orden: Record<Estado, number> = { down: 0, degraded: 1, unknown: 2, maintenance: 3, up: 4 };
    return [...porSitio.entries()].map(([sitio, rs]) => ({
      sitio,
      total: rs.length,
      peor: rs.reduce<Estado>((p, x) => (PESO[x.estado_actual] > PESO[p] ? x.estado_actual : p), 'up'),
      recursos: [...rs].sort((a, b) => orden[a.estado_actual] - orden[b.estado_actual]),
    })).sort((a, b) => PESO[b.peor] - PESO[a.peor] || a.sitio.localeCompare(b.sitio));
  });

  ngOnInit(): void {
    this.refrescar();
    this.pollSub = interval(environment.refreshMs).subscribe(() => this.refrescar());
    this.relojSub = interval(1000).subscribe(() => this.reloj.set(this.horaActual()));
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
    this.relojSub?.unsubscribe();
  }

  private refrescar(): void {
    this.svc.listar().subscribe({
      next: (p) => { this.recursos.set(p.data); this.enVivo.set(true); },
      error: () => this.enVivo.set(false),
    });
  }

  private horaActual(): string {
    return new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
}
