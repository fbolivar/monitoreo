import { JsonPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Chequeo, Incidencia, Metrica, Recurso } from '../../core/models';
import { RecursosService } from '../../core/recursos.service';
import { TelemetriaService } from '../../core/telemetria.service';
import { EstadoBadge } from '../../shared/estado-badge';
import { LineChart, Punto } from '../../shared/line-chart';
import { duracion, fecha, hace } from '../../shared/tiempo';

interface SerieMetrica { metrica: string; unidad: string; puntos: Punto[]; }

@Component({
  selector: 'app-recurso-detalle',
  standalone: true,
  imports: [RouterLink, JsonPipe, EstadoBadge, LineChart],
  templateUrl: './recurso-detalle.html',
  styleUrl: './recurso-detalle.scss',
})
export class RecursoDetalle {
  private route = inject(ActivatedRoute);
  private recursosSvc = inject(RecursosService);
  private tele = inject(TelemetriaService);

  id = 0;
  recurso = signal<Recurso | null>(null);
  ultimoChequeo = signal<Chequeo | null>(null);
  metricas = signal<Metrica[]>([]);
  incidencias = signal<Incidencia[]>([]);
  rango = signal<'1h' | '24h' | '7d'>('24h');
  cargando = signal(true);

  fecha = fecha;
  hace = hace;
  duracion = duracion;

  series = computed<SerieMetrica[]>(() => {
    const porMetrica = new Map<string, Metrica[]>();
    for (const m of this.metricas()) {
      (porMetrica.get(m.metrica) ?? porMetrica.set(m.metrica, []).get(m.metrica)!).push(m);
    }
    return [...porMetrica.entries()]
      .map(([metrica, ms]) => ({
        metrica,
        unidad: ms[0]?.unidad ?? '',
        puntos: ms.map((m) => ({ ts: m.ts, valor: m.valor })),
      }))
      .sort((a, b) => a.metrica.localeCompare(b.metrica));
  });

  constructor() {
    // Reacciona a cambios de :id (Angular reutiliza el componente entre recursos).
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe((pm) => {
      const id = Number(pm.get('id'));
      if (!Number.isFinite(id) || id <= 0) return;
      this.id = id;
      this.cargarTodo();
    });
  }

  private cargarTodo(): void {
    this.recurso.set(null);
    this.ultimoChequeo.set(null);
    this.incidencias.set([]);
    this.recursosSvc.obtener(this.id).subscribe({
      next: (r) => this.recurso.set(r),
      error: () => {},
    });
    this.tele.chequeos({ recurso_id: this.id, per_page: 1 }).subscribe({
      next: (p) => this.ultimoChequeo.set(p.data[0] ?? null),
    });
    this.tele.incidencias({ recurso_id: this.id, per_page: 50 }).subscribe({
      next: (p) => this.incidencias.set(p.data),
    });
    this.cargarMetricas();
  }

  cambiarRango(r: '1h' | '24h' | '7d'): void {
    this.rango.set(r);
    this.cargarMetricas();
  }

  private cargarMetricas(): void {
    this.cargando.set(true);
    const ms = { '1h': 3600, '24h': 86400, '7d': 604800 }[this.rango()];
    const desde = new Date(Date.now() - ms * 1000).toISOString();
    this.tele.metricas({ recurso_id: this.id, desde, per_page: 1000 }).subscribe({
      next: (p) => { this.metricas.set(p.data); this.cargando.set(false); },
      error: () => this.cargando.set(false),
    });
  }
}
